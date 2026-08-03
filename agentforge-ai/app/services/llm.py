"""LLM 客户端：OpenAI 兼容接口封装（DeepSeek/Qwen/Ollama）。

- 未配置 LLM_API_KEY 时进入 Mock 模式，保证本地开发不依赖外部服务。
- 通过 httpx 直连 {base_url}/chat/completions，避免 SDK 版本耦合。
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """调用 OpenAI 兼容 chat/completions，返回回答文本。"""
        if not self.available:
            return self.mock_chat(messages)

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - 统一转换为业务可读错误
            logger.error("LLM 调用失败: %s", exc)
            raise RuntimeError(f"LLM 调用失败: {exc}") from exc

    def mock_chat(self, messages: list[dict]) -> str:
        """Mock 回答：仅用于本地开发与联调，不产生真实费用。"""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return (
            "【Mock 模式】未配置 LLM_API_KEY，以下为模拟回答。\n\n"
            f"收到你的消息：{user_msg}\n\n"
            "配置环境变量 LLM_API_KEY 后即可获得真实模型回答。"
        )


llm_client = LLMClient()
