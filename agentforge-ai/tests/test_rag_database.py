"""数据库文件解析/结构化切片单元测试（设计 v0.2 §12.1）。

覆盖：SQLite 两表入库、单行超长独立成 chunk、CSV GBK 编码、损坏文件报错、
手动切片参数生效、非法参数校验、结构预览。
不依赖外部服务（Qdrant 用 FakeClient，Embedding 用哈希 Mock 降级路径）。
"""
import sqlite3

import pytest

from app.core.config import settings
from app.services import rag_service


def _make_sqlite(path, tables: dict[str, list[tuple]]) -> None:
    """构造 SQLite 测试库：tables = {表名: [列名...]: 行列表}。"""
    conn = sqlite3.connect(str(path))
    try:
        for name, (columns, rows) in tables.items():
            cols = ", ".join(f'"{c}"' for c in columns)
            conn.execute(f'CREATE TABLE "{name}" ({cols})')
            for row in rows:
                conn.execute(
                    f'INSERT INTO "{name}" VALUES ({",".join("?" * len(row))})', row)
        conn.commit()
    finally:
        conn.close()


# ---------------- SQLite 结构化切片 ----------------

class TestChunkDatabaseSqlite:
    def test_two_tables_each_10_rows(self, tmp_path):
        """两表各 10 行 → chunk 正确分组，元数据含 table/rowStart/rowEnd。"""
        db = tmp_path / "demo.db"
        rows = [(i, f"user{i}@x.com") for i in range(1, 11)]
        _make_sqlite(db, {"users": (["id", "email"], rows),
                          "orders": (["id", "amount"], [(i, i * 10.0) for i in range(1, 11)])})

        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=5)
        tables = [c["table"] for c in chunks]
        assert tables.count("users") == 2     # 10 行 / 每 chunk 5 行
        assert tables.count("orders") == 2
        users_chunks = [c for c in chunks if c["table"] == "users"]
        assert users_chunks[0]["rowStart"] == 1 and users_chunks[0]["rowEnd"] == 5
        assert users_chunks[1]["rowStart"] == 6 and users_chunks[1]["rowEnd"] == 10
        assert users_chunks[0]["content"].startswith("表 users，表头：id, email")
        assert "第 1 行" in users_chunks[0]["content"]
        assert "第 10 行" in users_chunks[1]["content"]
        assert all(c["sourceType"] == "sqlite" for c in chunks)

    def test_single_oversized_row_isolated(self, tmp_path):
        """单行超长（大字段）→ 独立成 chunk，不与其他行混切。"""
        db = tmp_path / "big.db"
        big_text = "字" * 5000  # 远超 chunk 上限（默认 500 token ≈ 750 字符）
        _make_sqlite(db, {"t": (["id", "blob"], [(1, "短"), (2, big_text), (3, "尾")])})

        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=50)
        assert len(chunks) == 3
        big = chunks[1]
        assert big["rowStart"] == 2 and big["rowEnd"] == 2
        assert "字" * 5000 in big["content"]

    def test_empty_tables_skipped(self, tmp_path):
        db = tmp_path / "empty.db"
        _make_sqlite(db, {"a": (["id"], []), "b": (["id"], [(1,)])})
        chunks = rag_service.chunk_database(str(db), "sqlite")
        assert len(chunks) == 1 and chunks[0]["table"] == "b"

    def test_rows_limit_exceeded_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "db_max_rows", 3)
        db = tmp_path / "limit.db"
        _make_sqlite(db, {"t": (["id"], [(i,) for i in range(1, 6)])})
        with pytest.raises(ValueError, match="超出上限"):
            rag_service.chunk_database(str(db), "sqlite")

    def test_corrupted_file_raises(self, tmp_path):
        """损坏/非 SQLite 文件 → 抛错（上游状态机据此置 FAILED，不悬挂）。"""
        f = tmp_path / "broken.db"
        f.write_bytes(b"not a sqlite file at all")
        with pytest.raises(Exception):  # noqa: BLE001 - sqlite3.DatabaseError
            list(rag_service._iter_sqlite_rows(str(f)))

    def test_manual_chunk_rows_applies(self, tmp_path):
        """手动切片：自定义每 chunk 行数生效。"""
        db = tmp_path / "manual.db"
        _make_sqlite(db, {"t": (["id"], [(i,) for i in range(1, 21)])})
        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=10)
        assert len(chunks) == 2
        assert chunks[0]["rowEnd"] == 10 and chunks[1]["rowStart"] == 11

    def test_exclude_tables_and_columns(self, tmp_path):
        db = tmp_path / "ex.db"
        _make_sqlite(db, {"keep": (["id", "secret"], [(1, "s")]),
                          "drop": (["id"], [(1,)])})
        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=10,
                                            exclude_tables=["drop"],
                                            exclude_columns=["secret"])
        assert len(chunks) == 1
        assert "secret" not in chunks[0]["content"]
        assert "id: 1" in chunks[0]["content"]

    def test_by_table_false_merges_tables(self, tmp_path):
        """byTable=False → 跨表连续切分，不按表边界冲刷（行文本自带表名可追溯）。"""
        db = tmp_path / "merge.db"
        _make_sqlite(db, {"users": (["id"], [(i,) for i in range(1, 4)]),
                          "orders": (["id"], [(i,) for i in range(1, 4)])})

        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=50,
                                            by_table=False)
        assert len(chunks) == 1
        assert "表 users，表头：" in chunks[0]["content"]
        assert "表 orders，表头：" in chunks[0]["content"]
        assert "表 orders，第 1 行" in chunks[0]["content"]
        # 行号区间覆盖两表真实行号（users 1-3 → orders 1-3）
        assert chunks[0]["rowStart"] == 1 and chunks[0]["rowEnd"] == 3

        # 默认 by_table=True 仍按表切分
        by_table_chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=50)
        assert len(by_table_chunks) == 2

    def test_row_end_accurate_when_empty_rows_skipped(self, tmp_path):
        """chunk 内跳过空行后，rowEnd 应为真实最后一行号，而非按计数推算。"""
        db = tmp_path / "skip.db"
        # 第 2 行全空（NULL + 空串）会被跳过
        _make_sqlite(db, {"t": (["id", "v"], [(1, "a"), (None, ""), (3, "c")])})

        chunks = rag_service.chunk_database(str(db), "sqlite", chunk_rows=10)
        assert len(chunks) == 1
        assert chunks[0]["rowStart"] == 1
        assert chunks[0]["rowEnd"] == 3
        assert "第 2 行" not in chunks[0]["content"]


# ---------------- CSV ----------------

class TestChunkDatabaseCsv:
    def test_utf8_csv(self, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text("姓名,城市\n张三,北京\n李四,上海\n", encoding="utf-8")
        chunks = rag_service.chunk_database(str(f), "csv", chunk_rows=10)
        assert len(chunks) == 1
        assert chunks[0]["table"] == ""
        assert chunks[0]["rowStart"] == 1 and chunks[0]["rowEnd"] == 2
        assert "姓名: 张三" in chunks[0]["content"]
        assert "城市: 北京" in chunks[0]["content"]

    def test_gbk_csv_no_garbled(self, tmp_path):
        """GBK 编码（中文 Excel 导出）→ 回退 GB18030，中文不乱码。"""
        f = tmp_path / "gbk.csv"
        f.write_bytes("姓名,城市\n张三,北京\n".encode("gbk"))
        chunks = rag_service.chunk_database(str(f), "csv", chunk_rows=10)
        assert "张三" in chunks[0]["content"]
        assert "北京" in chunks[0]["content"]

    def test_quoted_fields_with_commas(self, tmp_path):
        f = tmp_path / "q.csv"
        f.write_text('备注\n"含,逗号"\n', encoding="utf-8")
        chunks = rag_service.chunk_database(str(f), "csv", chunk_rows=10)
        assert "备注: 含,逗号" in chunks[0]["content"]

    def test_csv_no_rows_empty(self, tmp_path):
        f = tmp_path / "h.csv"
        f.write_text("仅表头,无数据\n", encoding="utf-8")
        assert rag_service.chunk_database(str(f), "csv") == []


# ---------------- 手动切片参数校验 ----------------

class TestResolveDbConfig:
    def test_auto_defaults(self):
        cfg = rag_service._resolve_db_config("auto", None)
        assert cfg["chunk_rows"] == settings.db_chunk_rows
        assert cfg["by_table"] is True

    def test_manual_valid(self):
        cfg = rag_service._resolve_db_config(
            "manual", {"chunkRows": 30, "excludeTables": ["logs"], "keepHeader": False})
        assert cfg["chunk_rows"] == 30
        assert cfg["exclude_tables"] == ["logs"]
        assert cfg["keep_header"] is False

    def test_invalid_chunk_rows_rejected(self):
        with pytest.raises(ValueError, match="每 chunk 行数需在"):
            rag_service._resolve_db_config("manual", {"chunkRows": 9999})
        with pytest.raises(ValueError, match="必须为整数"):
            rag_service._resolve_db_config("manual", {"chunkRows": "abc"})

    def test_invalid_exclude_type_rejected(self):
        with pytest.raises(ValueError, match="必须为字符串数组"):
            rag_service._resolve_db_config("manual", {"excludeTables": "users"})

    def test_text_config_validation(self):
        with pytest.raises(ValueError, match="chunkSizeTokens 需在"):
            rag_service._resolve_text_config({"chunkSizeTokens": 99999})
        cfg = rag_service._resolve_text_config({"chunkSizeTokens": 800, "chunkOverlapTokens": 50})
        assert cfg == {"size_tokens": 800, "overlap_tokens": 50}


# ---------------- 结构预览 ----------------

class TestParseDatabase:
    def test_sqlite_structure(self, tmp_path):
        db = tmp_path / "s.db"
        _make_sqlite(db, {"users": (["id", "name"], [(1, "a"), (2, "b")])})
        info = rag_service.parse_database(str(db), "sqlite")
        assert info["tableCount"] == 1
        assert info["tables"][0]["name"] == "users"
        assert info["tables"][0]["columns"] == ["id", "name"]
        assert info["tables"][0]["rowCount"] == 2
        assert info["totalRows"] == 2


# ---------------- ingest 全链路（Fake Qdrant） ----------------

class TestIngestDatabase:
    def test_sqlite_ingest_payload_metadata(self, tmp_path, monkeypatch):
        """SQLite 入库 → payload 含 table/rowStart/rowEnd/sourceType，chunk 数正确。"""
        import uuid as uuid_mod
        from app.services import rag_service as mod

        db = tmp_path / "d.db"
        _make_sqlite(db, {"users": (["id", "name"], [(i, f"u{i}") for i in range(1, 11)])})

        class FakeClient:
            def __init__(self):
                self.upserted = []

            def upsert(self, collection_name, points):
                self.upserted.extend(points)

        client = FakeClient()
        monkeypatch.setattr(mod, "_get_qdrant", lambda: client)
        monkeypatch.setattr(mod, "_ensure_collection", lambda *a, **k: None)
        monkeypatch.setattr(mod, "embed", lambda t: [0.1] * settings.embedding_dim)

        count = mod.ingest(1, "demo.db", str(db), slicing_mode="auto")
        assert count == len(client.upserted)
        assert count > 0
        for point in client.upserted:
            uuid_mod.UUID(point["id"])
            p = point["payload"]
            assert p["table"] == "users"
            assert p["sourceType"] == "sqlite"
            assert p["rowStart"] >= 1 and p["rowEnd"] >= p["rowStart"]

    def test_manual_ingest_applies_config(self, tmp_path, monkeypatch):
        from app.services import rag_service as mod

        db = tmp_path / "m.db"
        _make_sqlite(db, {"t": (["id"], [(i,) for i in range(1, 11)])})

        class FakeClient:
            def __init__(self):
                self.upserted = []

            def upsert(self, collection_name, points):
                self.upserted.extend(points)

        client = FakeClient()
        monkeypatch.setattr(mod, "_get_qdrant", lambda: client)
        monkeypatch.setattr(mod, "_ensure_collection", lambda *a, **k: None)
        monkeypatch.setattr(mod, "embed", lambda t: [0.1] * settings.embedding_dim)

        count = mod.ingest(1, "m.db", str(db),
                           slicing_mode="manual", slicing_config={"chunkRows": 10})
        assert count == 1  # 10 行 / 每 chunk 10 行 = 1 个 chunk
        assert client.upserted[0]["payload"]["rowEnd"] == 10

    def test_invalid_manual_config_not_ingested(self, tmp_path, monkeypatch):
        """手动切片非法参数 → 抛错，不产生任何 upsert。"""
        from app.services import rag_service as mod

        db = tmp_path / "bad.db"
        _make_sqlite(db, {"t": (["id"], [(1,)])})

        class FakeClient:
            def __init__(self):
                self.upserted = []

            def upsert(self, collection_name, points):
                self.upserted.extend(points)

        client = FakeClient()
        monkeypatch.setattr(mod, "_get_qdrant", lambda: client)
        monkeypatch.setattr(mod, "_ensure_collection", lambda *a, **k: None)
        monkeypatch.setattr(mod, "embed", lambda t: [0.1] * settings.embedding_dim)

        with pytest.raises(ValueError, match="每 chunk 行数需在"):
            mod.ingest(1, "bad.db", str(db),
                       slicing_mode="manual", slicing_config={"chunkRows": 99999})
        assert client.upserted == []

    def test_progress_callback_invoked(self, tmp_path, monkeypatch):
        """提供 progress_url 时回写进度（至少一次 totalChunks）。"""
        from app.services import rag_service as mod

        db = tmp_path / "p.db"
        _make_sqlite(db, {"t": (["id"], [(i,) for i in range(1, 11)])})

        class FakeClient:
            def __init__(self):
                self.upserted = []

            def upsert(self, collection_name, points):
                self.upserted.extend(points)

        calls = []

        class FakeResp:
            status_code = 200

        monkeypatch.setattr(mod, "_get_qdrant", lambda: FakeClient())
        monkeypatch.setattr(mod, "_ensure_collection", lambda *a, **k: None)
        monkeypatch.setattr(mod, "embed", lambda t: [0.1] * settings.embedding_dim)
        monkeypatch.setattr(
            mod.httpx, "post",
            lambda url, json, timeout, headers: calls.append((url, json, headers)) or FakeResp())

        mod.ingest(1, "p.db", str(db), progress_url="http://backend/api/file/9/progress",
                   document_id=9)
        assert calls
        assert all(c[0].endswith("/9/progress") for c in calls)
        assert any("totalChunks" in c[1] for c in calls)
        # 后端内部接口强制校验 X-Internal-Token，回调必须携带
        assert all(c[2].get("X-Internal-Token") == settings.internal_token for c in calls)
