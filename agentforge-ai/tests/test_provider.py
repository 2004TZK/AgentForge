"""M4 多模型配置测试：LLMClient 请求级 Provider 覆盖（base_url/api_key/local 分流）。"""
from app.services.llm import LLMClient


class TestProviderOverride:
    def test_provider_overrides_base_url_and_key(self):
        """请求级 Provider 覆盖 base_url 与 api_key，且不影响默认值。"""
        client = LLMClient({"type": "openai", "baseUrl": "https://api.deepseek.com/v1/",
                            "apiKey": "sk-test"})
        assert client.base_url == "https://api.deepseek.com/v1"  # 尾部斜杠被归一化
        assert client.api_key == "sk-test"
        assert client.local is False  # openai → 远端 OpenAI 兼容路径

    def test_ollama_provider_uses_native_path(self):
        client = LLMClient({"type": "ollama", "baseUrl": "http://ollama:11434", "apiKey": None})
        assert client.local is True
        # 本地模型无 Key 也可用
        assert client.available is True

    def test_provider_missing_falls_back_to_env(self):
        """无 Provider 时回落环境变量（默认本地 Ollama）。"""
        client = LLMClient(None)
        assert client.local is True  # settings.llm_local 默认 True（本地部署）
