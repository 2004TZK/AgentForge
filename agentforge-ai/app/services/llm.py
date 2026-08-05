"""LLM 客户端：OpenAI 兼容接口封装（DeepSeek/Qwen/Ollama）。

- 未配置 LLM_API_KEY 且非本地模型地址时进入 Mock 模式（本地开发不依赖外部服务）
- 失败统一抛出结构化错误（LLMTimeoutError / LLMUnavailableError / LLMModelError，
  见 core/errors.py），由 FastAPI 异常处理器转为 {"code", "message"} 响应，
  后端据此映射 30001/30002/30003 错误码
- 通过 httpx 直连 {base_url}/chat/completions，避免 SDK 版本耦合
"""
import asyncio
import json
import logging

import httpx

from app.core.config import settings
from app.core.errors import AiServiceError, LLMModelError, LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

# Mock 流式回答的切块大小（制造打字机效果，便于本地演示流式链路）
_MOCK_CHUNK_SIZE = 12


class LLMClient:
    def __init__(self, provider: dict | None = None) -> None:
        """M4 多模型配置：provider 为请求级覆盖 {type, baseUrl, apiKey}，
        缺省回落环境变量（保持本地开发与旧调用兼容）。"""
        p = provider or {}
        self.base_url = (p.get("baseUrl") or settings.llm_base_url).rstrip("/")
        self.api_key = p.get("apiKey") if p.get("apiKey") else settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        # 请求级显式指定的 Provider 类型（ollama/openai）；未指定时动态读环境变量
        self._provider_type = p.get("type") or None

    @property
    def local(self) -> bool:
        """本地（Ollama）走原生 /api/chat（think 可控）；远端走 OpenAI 兼容。
        请求级 Provider 显式指定时以它为准；否则动态读环境变量（便于测试 monkeypatch）。"""
        if self._provider_type:
            return self._provider_type == "ollama"
        return settings.llm_local

    @property
    def available(self) -> bool:
        """本地模型（如 Ollama）不配置 API Key 也可调用；远端模型仍需 Key。
        容器内 base_url 可能是服务名（如 http://ollama:11434/v1），故以 LLM_LOCAL 显式标记本地部署。"""
        if self.api_key:
            return True
        return self.local and bool(self.base_url)

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """同步调用 chat/completions，返回回答文本。"""
        if not self.available:
            return self.mock_chat(messages)
        if self.local:
            return self._chat_native(messages, temperature)
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, temperature),
                timeout=self.timeout,
            )
            self._raise_for_llm(resp)
            try:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMModelError(f"模型返回格式异常: {exc}") from exc
        except AiServiceError:  # noqa: BLE001 - 已结构化的错误直接透传
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    def _chat_native(self, messages: list[dict], temperature: float) -> str:
        """Ollama 原生 /api/chat（本地模型专用）。

        说明：Ollama 的 OpenAI 兼容 /v1/chat/completions 不识别 think 参数，
        qwen3.5 等推理模型会持续产出大量思考 token 导致响应极慢；
        原生接口支持 think=false（见配置 llm_think），聊天响应可提升 10 倍以上。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": settings.llm_think,
            "options": {"temperature": temperature},
        }
        try:
            resp = httpx.post(f"{self._native_base()}/api/chat",
                              headers=self._headers(), json=payload, timeout=self.timeout)
            self._raise_for_llm(resp)
            try:
                return resp.json()["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMModelError(f"模型返回格式异常: {exc}") from exc
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7):
        """流式调用 chat/completions（stream=true），逐块产出内容增量。

        M1 仅流式输出回答文本；工具/RAG 上下文在流式前完成，Phase 4 演进为图内流式。
        """
        if not self.available:
            text = self.mock_chat(messages)
            for i in range(0, len(text), _MOCK_CHUNK_SIZE):
                await asyncio.sleep(0.02)
                yield text[i : i + _MOCK_CHUNK_SIZE]
            return
        if self.local:
            async for delta in self._chat_stream_native(messages, temperature):
                yield delta
            return
        payload = self._payload(messages, temperature)
        payload["stream"] = True
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions",
                    headers=self._headers(), json=payload,
                ) as resp:
                    self._raise_for_llm(resp)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            return
                        try:
                            delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                        except (KeyError, IndexError, ValueError):
                            logger.warning("忽略异常流式分块: %s", chunk[:200])
                            continue
                        if delta:
                            yield delta
        except AiServiceError:  # noqa: BLE001
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型流式调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    async def _chat_stream_native(self, messages: list[dict], temperature: float):
        """Ollama 原生 /api/chat 流式（本地模型专用，think 可控，见 _chat_native 说明）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": settings.llm_think,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self._native_base()}/api/chat",
                    headers=self._headers(), json=payload,
                ) as resp:
                    self._raise_for_llm(resp)
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            logger.warning("忽略异常流式分块: %s", line[:200])
                            continue
                        if data.get("done"):
                            return
                        delta = data.get("message", {}).get("content", "")
                        if delta:
                            yield delta
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型流式调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    # ---------------- 工具调用（M3 Phase 4：LLM 依据 Schema 自主选择） ----------------

    def chat_with_tools(self, messages: list[dict], tools: list[dict],
                        temperature: float = 0.7) -> dict:
        """携带工具 Schema 调用模型，返回 {"content": str, "tool_calls": [...]}。

        tool_calls 归一化为 [{"name", "arguments": dict, "tool_call_id"?: str}]，
        供 ReAct 循环直接执行。本地模型走 Ollama 原生 /api/chat（tools 与 think 并存），
        远端模型走 OpenAI 兼容 /chat/completions。
        """
        if not tools:
            return {"content": self.chat(messages, temperature), "tool_calls": []}
        if not self.available:
            return {"content": self.mock_chat(messages), "tool_calls": []}
        if self.local:
            return self._chat_native_tools(messages, tools, temperature)
        return self._chat_openai_tools(messages, tools, temperature)

    async def chat_stream_with_tools(self, messages: list[dict], tools: list[dict],
                                     temperature: float = 0.7):
        """流式工具调用：逐块产出 {"type": "delta", "content"} 事件，
        结束产出 {"type": "done", "content": 全文, "tool_calls": [...]} 事件。

        工具调用轮通常无内容增量（模型直接输出 tool_calls）；文本轮增量照常输出。
        """
        if not tools:
            full = ""
            async for delta in self.chat_stream(messages, temperature):
                full += delta
                yield {"type": "delta", "content": delta}
            yield {"type": "done", "content": full, "tool_calls": []}
            return
        if not self.available:
            text = self.mock_chat(messages)
            for i in range(0, len(text), _MOCK_CHUNK_SIZE):
                await asyncio.sleep(0.02)
                yield {"type": "delta", "content": text[i : i + _MOCK_CHUNK_SIZE]}
            yield {"type": "done", "content": text, "tool_calls": []}
            return
        if self.local:
            async for event in self._stream_native_tools(messages, tools, temperature):
                yield event
            return
        async for event in self._stream_openai_tools(messages, tools, temperature):
            yield event

    def _chat_native_tools(self, messages: list[dict], tools: list[dict],
                           temperature: float) -> dict:
        """Ollama 原生 /api/chat + tools（本地模型专用，think 可控，见 _chat_native 说明）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": settings.llm_think,
            "options": {"temperature": temperature},
        }
        try:
            resp = httpx.post(f"{self._native_base()}/api/chat",
                              headers=self._headers(), json=payload, timeout=self.timeout)
            self._raise_for_llm(resp)
            try:
                message = resp.json()["message"]
                return self._normalize_tool_message(message, has_tool_call_id=False)
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMModelError(f"模型返回格式异常: {exc}") from exc
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    def _chat_openai_tools(self, messages: list[dict], tools: list[dict],
                           temperature: float) -> dict:
        """OpenAI 兼容 /chat/completions + tools（远端模型；本地 qwen3.5 不走此路径）。"""
        payload = self._payload(messages, temperature)
        payload["tools"] = tools
        try:
            resp = httpx.post(f"{self.base_url}/chat/completions",
                              headers=self._headers(), json=payload, timeout=self.timeout)
            self._raise_for_llm(resp)
            try:
                message = resp.json()["choices"][0]["message"]
                return self._normalize_tool_message(message, has_tool_call_id=True)
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMModelError(f"模型返回格式异常: {exc}") from exc
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    async def _stream_native_tools(self, messages: list[dict], tools: list[dict],
                                   temperature: float):
        """Ollama 原生 /api/chat 流式 + tools：增量事件 + 结束事件（含 tool_calls）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": True,
            "think": settings.llm_think,
            "options": {"temperature": temperature},
        }
        full = ""
        tool_calls: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self._native_base()}/api/chat",
                    headers=self._headers(), json=payload,
                ) as resp:
                    self._raise_for_llm(resp)
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            logger.warning("忽略异常流式分块: %s", line[:200])
                            continue
                        message = data.get("message", {})
                        delta = message.get("content", "")
                        if delta:
                            full += delta
                            yield {"type": "delta", "content": delta}
                        for tc in message.get("tool_calls", []) or []:
                            tool_calls.append(self._normalize_tool_call(
                                tc.get("function", {}), has_tool_call_id=False))
                        if data.get("done"):
                            break
            yield {"type": "done", "content": full, "tool_calls": tool_calls}
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型流式调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    async def _stream_openai_tools(self, messages: list[dict], tools: list[dict],
                                   temperature: float):
        """OpenAI 兼容流式 + tools：增量事件 + 结束事件（远端模型路径）。"""
        payload = self._payload(messages, temperature)
        payload["tools"] = tools
        payload["stream"] = True
        full = ""
        # OpenAI 流式协议的 tool_calls 为增量：首个 chunk 带 id+name+空 arguments，
        # 后续 chunk 仅携带 arguments 片段（无 id/name）。须按 index 累积拼接，
        # 否则碎片会被当成完整调用（name 为空 → 工具未注册、参数残缺 → 执行报错）。
        pending: dict[int, dict] = {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions",
                    headers=self._headers(), json=payload,
                ) as resp:
                    self._raise_for_llm(resp)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = json.loads(chunk)["choices"][0]["delta"]
                        except (KeyError, IndexError, ValueError):
                            logger.warning("忽略异常流式分块: %s", chunk[:200])
                            continue
                        content = delta.get("content")
                        if content:
                            full += content
                            yield {"type": "delta", "content": content}
                        for tc in delta.get("tool_calls", []) or []:
                            idx = tc.get("index", 0)
                            slot = pending.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"]
            tool_calls = [
                LLMClient._normalize_tool_call(
                    {"name": slot["name"], "arguments": slot["arguments"]},
                    has_tool_call_id=True, tool_call_id=slot["id"] or None,
                )
                for slot in (pending[i] for i in sorted(pending))
            ]
            yield {"type": "done", "content": full, "tool_calls": tool_calls}
        except AiServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"模型流式调用超时（{self.timeout}s）") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"模型服务连接失败: {exc}") from exc

    @staticmethod
    def _normalize_tool_message(message: dict, has_tool_call_id: bool) -> dict:
        """归一化模型返回的 message：提取 content 与 tool_calls（Ollama/OpenAI 格式差异）。"""
        tool_calls = []
        for tc in message.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            tool_calls.append(LLMClient._normalize_tool_call(
                fn, has_tool_call_id=has_tool_call_id, tool_call_id=tc.get("id")))
        return {"content": message.get("content") or "", "tool_calls": tool_calls}

    @staticmethod
    def _normalize_tool_call(fn: dict, has_tool_call_id: bool, tool_call_id=None) -> dict:
        """归一化单个 tool_call：arguments 兼容字符串/dict，附加 tool_call_id（OpenAI 协议回填用）。"""
        name = fn.get("name", "")
        arguments = fn.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = {"_raw": arguments}
        if not isinstance(arguments, dict):
            arguments = {"_raw": str(arguments)}
        call = {"name": name, "arguments": arguments}
        if has_tool_call_id:
            call["tool_call_id"] = tool_call_id
        return call

    def mock_chat(self, messages: list[dict]) -> str:
        """Mock 回答：仅用于本地开发与联调，不产生真实费用。"""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return (
            "【Mock 模式】未配置 LLM_API_KEY 且未使用本地模型，以下为模拟回答。\n\n"
            f"收到你的消息：{user_msg}\n\n"
            "配置 LLM_API_KEY 或使用本地模型地址（如 http://localhost:11434/v1）后即可获得真实回答。"
        )

    # ---------------- 私有方法 ----------------

    def _payload(self, messages: list[dict], temperature: float) -> dict:
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        # Ollama 本地推理模型（qwen3.5 等）默认开启思考模式会先产出大量推理 token，
        # 聊天场景极慢；仅本地模型传递 think 参数，远端 OpenAI 兼容服务不发送
        if self.local:
            payload["think"] = settings.llm_think
        return payload

    def _headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _native_base(self) -> str:
        """原生 API 基址：llm_base_url 去掉末尾 /v1（兼容 http://localhost:11434/v1 写法）。"""
        base = self.base_url.rstrip("/")
        return base[:-3] if base.endswith("/v1") else base

    @staticmethod
    def _raise_for_llm(resp: httpx.Response) -> None:
        """HTTP 错误转为模型错误；尽量透出错误体的可读信息（如 Ollama 模型未拉取提示）。"""
        if resp.is_success:
            return
        detail = ""
        try:
            body = resp.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                detail = str(err.get("message", ""))
            elif err:
                detail = str(err)
        except ValueError:
            detail = resp.text[:200]
        raise LLMModelError(
            f"模型服务返回 HTTP {resp.status_code}" + (f"：{detail}" if detail else "")
        )


llm_client = LLMClient()
