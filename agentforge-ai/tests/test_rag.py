"""RAG 单元测试：切分、解析、Embedding 维度校验、集合维度校验、空知识库降级。

运行：cd agentforge-ai && pytest tests -q
说明：不依赖外部服务（Qdrant/Ollama 均用 mock/降级路径）。
"""
import pytest

from app.core.config import settings
from app.services import agent_runtime, rag_service


# ---------------- 切分 ----------------

class TestChunkText:
    def test_empty_text_returns_empty(self):
        assert rag_service.chunk_text("   ") == []

    def test_chunk_size_and_overlap(self, monkeypatch):
        monkeypatch.setattr(settings, "chunk_size_tokens", 100)    # 100 token ≈ 150 字符
        monkeypatch.setattr(settings, "chunk_overlap_tokens", 50)  # 50 token ≈ 75 字符重叠
        text = "词" * 500
        chunks = rag_service.chunk_text(text)
        assert len(chunks) > 1
        assert all(len(c) <= 150 for c in chunks)
        # 相邻块存在重叠（后块前缀 == 前块尾部）
        assert chunks[0][-75:] == chunks[1][:75]

    def test_overlap_capped_at_half_size(self, monkeypatch):
        monkeypatch.setattr(settings, "chunk_size_tokens", 100)
        monkeypatch.setattr(settings, "chunk_overlap_tokens", 90)  # 超过一半 → 截断
        text = "词" * 500
        chunks = rag_service.chunk_text(text)
        assert len(chunks) > 1


# ---------------- 解析 ----------------

class TestParseFile:
    def test_txt(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("第一行\n第二行", encoding="utf-8")
        assert rag_service.parse_file(str(f)) == "第一行\n第二行"

    def test_md(self, tmp_path):
        f = tmp_path / "b.md"
        f.write_text("# 标题", encoding="utf-8")
        assert rag_service.parse_file(str(f)) == "# 标题"

    def test_unsupported_type(self, tmp_path):
        f = tmp_path / "c.exe"
        f.write_bytes(b"x")
        with pytest.raises(ValueError):
            rag_service.parse_file(str(f))

    def test_pdf_injects_page_markers(self, monkeypatch, tmp_path):
        """PDF 每页文本注入「第 N 页」标记（pypdf 用假对象替代）。"""
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            pages = [FakePage("第一页内容"), FakePage(""), FakePage("第三页内容")]

        import pypdf
        # parse_file 内部为「from pypdf import PdfReader」，需 patch pypdf 模块本身
        monkeypatch.setattr(pypdf, "PdfReader", lambda *a, **k: FakeReader())
        text = rag_service.parse_file(str(tmp_path / "d.pdf"))
        assert "【第 1 页】" in text
        assert "【第 3 页】" in text
        assert "【第 2 页】" not in text  # 空页跳过


# ---------------- Embedding 维度校验 ----------------

class TestEmbedRemote:
    def test_dimension_mismatch_raises_readable_error(self, monkeypatch):
        """模型返回维度与 EMBEDDING_DIM 不符时给出可读错误（引导改配置/重建）。"""
        monkeypatch.setattr(settings, "embedding_model", "bge-m3")
        monkeypatch.setattr(settings, "embedding_dim", 1024)

        class FakeResp:
            status_code = 200
            headers = {"content-type": "application/json"}

            def json(self):
                return {"data": [{"embedding": [0.1] * 768}]}  # 模型实际 768 维

        monkeypatch.setattr(rag_service.httpx, "post", lambda *a, **k: FakeResp())
        with pytest.raises(RuntimeError, match="维度不一致"):
            rag_service.embed("测试文本")

    def test_http_error_raises_readable_error(self, monkeypatch):
        monkeypatch.setattr(settings, "embedding_model", "bge-m3")

        class FakeResp:
            status_code = 404
            text = "model not found"
            headers = {"content-type": "application/json"}

            def json(self):
                return {"error": {"message": "model 'bge-m3' not found, try pulling it first"}}

        monkeypatch.setattr(rag_service.httpx, "post", lambda *a, **k: FakeResp())
        with pytest.raises(RuntimeError, match="HTTP 404"):
            rag_service.embed("测试文本")


# ---------------- 集合维度校验 ----------------

class TestEnsureCollection:
    def test_dimension_mismatch_raises(self, monkeypatch):
        """集合已存在但维度与配置不符 → 报错提示重建。"""
        monkeypatch.setattr(settings, "embedding_dim", 1024)

        class FakeCollection:
            class Params:
                vectors = type("V", (), {"size": 384})()
            config = type("C", (), {"params": Params()})()

        class FakeQdrant:
            def get_collection(self, name):
                return FakeCollection()

            def create_collection(self, **kwargs):
                raise AssertionError("不应创建集合")

        with pytest.raises(RuntimeError, match="重建"):
            rag_service._ensure_collection(FakeQdrant(), 1)

    def test_missing_collection_creates(self, monkeypatch):
        monkeypatch.setattr(settings, "embedding_dim", 1024)

        class FakeQdrant:
            def __init__(self):
                self.created = []

            def get_collection(self, name):
                raise Exception("not found")  # noqa: BLE001 - 模拟集合不存在

            def create_collection(self, **kwargs):
                self.created.append(kwargs)

        client = FakeQdrant()
        rag_service._ensure_collection(client, 1)
        assert client.created[0]["vectors_config"]["size"] == 1024


# ---------------- 检索增强 QA 降级 ----------------

class TestPrepareChatDegradation:
    def test_empty_knowledge_base_degrades(self, monkeypatch):
        """空知识库（无命中）→ 消息序列不携带上下文，正常对话。"""
        monkeypatch.setattr(rag_service, "search", lambda *a, **k: [])
        messages, tool_calls, sources = agent_runtime.prepare_chat(
            agent_id=1, message="你好", tools=[])
        assert "附加上下文" not in messages[-1]["content"]
        assert sources == []

    def test_search_failure_degrades(self, monkeypatch):
        """检索异常（Qdrant 不可用）→ 不阻断主链路，降级普通对话。"""
        def boom(*a, **k):
            raise RuntimeError("Qdrant 不可用")
        monkeypatch.setattr(rag_service, "search", boom)
        messages, tool_calls, sources = agent_runtime.prepare_chat(
            agent_id=1, message="你好", tools=[])
        assert "附加上下文" not in messages[-1]["content"]
        assert sources == []

    def test_hits_build_sources_with_snippet(self, monkeypatch):
        """命中知识库 → 上下文注入 + 来源含片段与分数。"""
        monkeypatch.setattr(rag_service, "search",
                            lambda *a, **k: [{"file": "指南.md", "content": "片段内容", "score": 0.9}])
        messages, tool_calls, sources = agent_runtime.prepare_chat(
            agent_id=1, message="如何配置", tools=[])
        assert "附加上下文" in messages[-1]["content"]
        assert sources[0]["file"] == "指南.md"
        assert sources[0]["snippet"] == "片段内容"
        assert sources[0]["score"] == 0.9


# ---------------- 入库 point ID 回归 ----------------

class TestIngestPointId:
    def test_point_ids_are_valid_uuids(self, monkeypatch):
        """Qdrant 新版本要求 point ID 为无符号整数或 UUID（回归：字符串 ID 被拒）。"""
        import uuid as uuid_mod
        from app.services import rag_service as mod

        class FakeClient:
            def __init__(self):
                self.upserted = []

            def upsert(self, collection_name, points):
                self.upserted.extend(points)

        client = FakeClient()
        monkeypatch.setattr(mod, "_get_qdrant", lambda: client)
        monkeypatch.setattr(mod, "_ensure_collection", lambda *a, **k: None)
        monkeypatch.setattr(mod, "parse_file", lambda p: "测试内容" * 200)
        monkeypatch.setattr(mod, "embed", lambda t: [0.1] * settings.embedding_dim)

        count = mod.ingest(1, "a.md", "/tmp/x.md")
        assert count == len(client.upserted)
        assert count > 1  # 长文本切出多个分块
        for point in client.upserted:
            uuid_mod.UUID(point["id"])  # 非法 UUID 会抛 ValueError
