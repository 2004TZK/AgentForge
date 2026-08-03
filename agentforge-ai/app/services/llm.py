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
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    @property
    def available(self) -> bool:
        """本地模型（如 Ollama）不配置 API Key 也可调用；远端模型仍需 Key。"""
        if self.api_key:
            return True
        return "localhost" in self.base_url or "127.0.0.1" in self.base_url

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """同步调用 chat/completions，返回回答文本。"""
        if not self.available:
            return self.mock_chat(messages)
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
        return {"model": self.model, "messages": messages, "temperature": temperature}

    def _headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

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
