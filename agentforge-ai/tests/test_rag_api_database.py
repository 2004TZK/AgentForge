"""RAG API 集成测试：/rag/preview 预览 + /rag/ingest 手动切片链路（设计 v0.2 §12.2）。

运行：cd agentforge-ai && pytest tests/test_rag_api_database.py -q
说明：Qdrant 用 FakeClient 替代，验证 HTTP 协议层（鉴权、参数校验、响应结构）。
"""
import sqlite3

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import rag_service

client = TestClient(app)
TOKEN = settings.internal_token


def _make_sqlite(path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute('CREATE TABLE "users" ("id" INTEGER, "name" TEXT)')
        conn.executemany("INSERT INTO users VALUES (?, ?)",
                         [(1, "张三"), (2, "李四"), (3, "王五")])
        conn.commit()
    finally:
        conn.close()


def _put_file(tmp_path, file_name: str) -> str:
    """在模拟共享卷放一个 SQLite 文件，返回相对路径。"""
    import shutil
    rel_dir = tmp_path / "1"
    rel_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "src" / file_name
    src.parent.mkdir(parents=True, exist_ok=True)
    _make_sqlite(src)
    target = rel_dir / file_name
    shutil.copyfile(src, target)
    return f"1/{file_name}"


def test_preview_requires_token():
    resp = client.post("/rag/preview", json={"fileName": "a.db", "filePath": "1/a.db"})
    assert resp.status_code == 401


def test_preview_returns_structure_and_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    rel = _put_file(tmp_path, "demo.db")
    resp = client.post("/rag/preview",
                       json={"fileName": "demo.db", "filePath": rel,
                             "slicingMode": "manual",
                             "slicingConfig": {"chunkRows": 2}},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sourceType"] == "sqlite"
    assert data["tableCount"] == 1
    assert data["tables"][0]["name"] == "users"
    assert data["tables"][0]["rowCount"] == 3
    assert len(data["sampleChunks"]) == 2      # 3 行 / 每 chunk 2 行 → 2 个 chunk
    assert data["sampleChunks"][0]["rowStart"] == 1
    assert data["sampleChunks"][0]["rowEnd"] == 2
    assert data["sampleChunks"][1]["rowStart"] == 3


def test_preview_invalid_config_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    rel = _put_file(tmp_path, "bad.db")
    resp = client.post("/rag/preview",
                       json={"fileName": "bad.db", "filePath": rel,
                             "slicingConfig": {"chunkRows": 99999}},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 400
    assert "每 chunk 行数" in resp.json()["detail"]


def test_preview_missing_file_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    resp = client.post("/rag/preview",
                       json={"fileName": "nope.db", "filePath": "1/nope.db"},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 400
    assert "文件不存在" in resp.json()["detail"]


def test_ingest_manual_slicing_via_api(tmp_path, monkeypatch):
    """HTTP 链路：手动切片参数透传 → 按参数入库（Fake Qdrant 校验 payload）。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    rel = _put_file(tmp_path, "api.db")

    class FakeClient:
        def __init__(self):
            self.upserted = []

        def upsert(self, collection_name, points):
            self.upserted.extend(points)

    fake = FakeClient()
    monkeypatch.setattr(rag_service, "_get_qdrant", lambda: fake)
    monkeypatch.setattr(rag_service, "_ensure_collection", lambda *a, **k: None)
    monkeypatch.setattr(rag_service, "embed", lambda t: [0.1] * settings.embedding_dim)

    resp = client.post("/rag/ingest",
                       json={"agentId": 1, "fileName": "api.db", "filePath": rel,
                             "slicingMode": "manual", "slicingConfig": {"chunkRows": 2}},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["chunkCount"] == 2          # 3 行 / 每 chunk 2 行 → 2 个 chunk
    assert len(fake.upserted) == 2
    assert fake.upserted[0]["payload"]["rowEnd"] == 2
    assert fake.upserted[1]["payload"]["rowStart"] == 3


def test_ingest_invalid_config_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    rel = _put_file(tmp_path, "reject.db")
    resp = client.post("/rag/ingest",
                       json={"agentId": 1, "fileName": "reject.db", "filePath": rel,
                             "slicingMode": "manual", "slicingConfig": {"chunkRows": "x"}},
                       headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 400
