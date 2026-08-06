"""自定义工具核心逻辑测试（本地运行，不依赖外部服务）。

- HTTP 模板渲染
- SSRF 防护（内网拒绝）
- HTTP 执行器真实请求（本地 http.server，临时关闭 SSRF）
- 自定义工具请求级 schema 生成 + handler 构建（不污染全局注册表）
- script 执行器在 sandbox 不可用时的可读错误
"""
import http.server
import json
import socket
import threading
import urllib.parse

import pytest

from app.core.config import settings
from app.tools import http_tool, registry, script_tool


def test_render_template():
    rendered = http_tool.render_template(
        {"url": "https://x.com/{city}?q={q}", "n": "{n}", "keep": 42},
        {"city": "北京", "q": "a b", "n": 3},
    )
    assert rendered == {"url": "https://x.com/北京?q=a b", "n": "3", "keep": 42}


def test_ssrf_blocked():
    for url in (
        "http://127.0.0.1/admin",
        "http://192.168.1.1/x",
        "http://169.254.169.254/latest/meta-data",
    ):
        with pytest.raises(ValueError):
            http_tool.check_ssrf(url)


def test_http_execute_local():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"path": self.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    old = settings.http_tool_ssrf_enabled
    settings.http_tool_ssrf_enabled = False
    try:
        result = http_tool.execute(
            {"method": "GET", "url": f"http://127.0.0.1:{port}/w/{{city}}",
             "query": {"q": "{q}"}, "timeoutSeconds": 5},
            {"city": "北京", "q": "测试"},
        )
        decoded = urllib.parse.unquote(result)
        assert "/w/北京" in decoded and "q=测试" in decoded
    finally:
        settings.http_tool_ssrf_enabled = old
        server.shutdown()


def test_custom_tool_request_scoped():
    definition = {
        "name": "my_test_tool",
        "description": "测试工具",
        "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
        "scriptConfig": {"language": "python", "source": "def run(args):\n    return args"},
    }
    tools = registry.openai_tools(["my_test_tool"], [definition])
    assert any(t["function"]["name"] == "my_test_tool" for t in tools)
    # 自定义工具仅由请求级定义生成，不写入全局注册表（避免并发串扰）
    assert "my_test_tool" not in registry.TOOL_REGISTRY
    handler = registry.build_custom_handler(definition)
    assert callable(handler)


def test_script_sandbox_down():
    old = settings.sandbox_base_url
    settings.sandbox_base_url = "http://127.0.0.1:1"
    try:
        with pytest.raises(ConnectionError, match="沙箱执行器不可用"):
            script_tool.execute(
                {"language": "python", "source": "def run(args): return 1"}, {})
    finally:
        settings.sandbox_base_url = old
