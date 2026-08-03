"""AI 服务冒烟测试：健康检查、鉴权、Mock 对话、工具求值。

运行：cd agentforge-ai && pytest tests -q
说明：不依赖外部服务（Qdrant/Redis 可缺失，走降级路径）。
"""
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)
TOKEN = settings.internal_token


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_chat_requires_token():
    resp = client.post("/agent/chat", json={"agentId": 1, "message": "hi"})
    assert resp.status_code == 401


def test_chat_mock_mode(monkeypatch):
    # 决策 v1.4：默认远端云端（LLM_LOCAL=false）；Mock 测试需指向非本地地址
    from app.core.config import settings
    from app.services.llm import llm_client
    monkeypatch.setattr(llm_client, "base_url", "https://api.example.com")
    monkeypatch.setattr(settings, "llm_local", False)
    resp = client.post("/agent/chat",
                       json={"agentId": 1, "message": "你好"},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "【Mock 模式】" in data["answer"]


def test_rag_requires_token():
    resp = client.post("/rag/ingest", json={"agentId": 1, "fileName": "a.md", "filePath": "x.md"})
    assert resp.status_code == 401


def test_calculator_evaluate():
    from app.tools.calculator import evaluate
    assert evaluate("2 + 3 * 4") == 14.0


def test_calculator_rejects_code():
    from app.tools.calculator import evaluate
    try:
        evaluate("__import__('os').system('echo hi')")
        raise AssertionError("应拒绝非法表达式")
    except ValueError:
        pass
