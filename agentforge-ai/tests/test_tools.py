"""M3 工具层测试：Schema 转换、新工具（current_time/web_search）、工具元数据接口。

运行：cd agentforge-ai && pytest tests -q
说明：不依赖外部服务。
"""
import re

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.tools import registry as tool_registry

client = TestClient(app)
TOKEN = settings.internal_token


# ---------------- Schema 转换 ----------------

class TestOpenAiSchema:
    def test_to_openai_tool_structure(self):
        tool = tool_registry.to_openai_tool("calculator")
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"] == "calculator"
        assert fn["parameters"]["type"] == "object"
        assert "expression" in fn["parameters"]["properties"]
        assert fn["parameters"]["required"] == ["expression"]

    def test_optional_param_not_required(self):
        tool = tool_registry.to_openai_tool("current_time")
        assert "time_format" in tool["function"]["parameters"]["properties"]
        assert "required" not in tool["function"]["parameters"]  # 全可选参数不出 required

    def test_openai_tools_filters_unregistered(self):
        tools = tool_registry.openai_tools(["calculator", "no_such_tool"])
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "calculator"


# ---------------- 新工具 ----------------

class TestCurrentTime:
    def test_default_format(self):
        result = tool_registry.call_tool("current_time", {})
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result)

    def test_custom_format(self):
        result = tool_registry.call_tool("current_time", {"time_format": "%Y"})
        assert re.fullmatch(r"\d{4}", result)

    def test_invalid_format_fails_gracefully(self):
        result = tool_registry.call_tool("current_time", {"time_format": "%Q"})
        assert "失败" in result  # ValueError → 失败文本（不抛异常）


class TestWebSearch:
    def test_without_key_returns_placeholder(self, monkeypatch):
        monkeypatch.delenv("WEB_SEARCH_API_KEY", raising=False)
        result = tool_registry.call_tool("web_search", {"query": "spring"})
        assert "not_configured" in result
        assert "API Key" in result

    def test_with_config_key_returns_results(self):
        result = tool_registry.call_tool(
            "web_search", {"query": "spring"}, {"api_key": "test-key"})
        assert "results" in result
        assert "spring" in result

    def test_with_env_key(self, monkeypatch):
        monkeypatch.setenv("WEB_SEARCH_API_KEY", "env-key")
        result = tool_registry.call_tool("web_search", {"query": "x"})
        assert "results" in result


# ---------------- 元数据接口 ----------------

class TestToolsMetaApi:
    def test_requires_token(self):
        resp = client.get("/agent/tools/meta")
        assert resp.status_code == 401

    def test_meta_contains_all_tools(self):
        resp = client.get("/agent/tools/meta", headers={"X-Internal-Token": TOKEN})
        assert resp.status_code == 200
        data = resp.json()
        names = {t["name"] for t in data}
        assert {"calculator", "github", "current_time", "web_search"} <= names
        calc = next(t for t in data if t["name"] == "calculator")
        assert "expression" in calc["parameters"]
        search = next(t for t in data if t["name"] == "web_search")
        assert "api_key" in search["config"]  # 前端按 config Schema 渲染配置表单
