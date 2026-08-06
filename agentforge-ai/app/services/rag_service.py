"""RAG 服务：解析 → 切分 → Embedding → Qdrant 检索。

- Qdrant collection 按智能体隔离：agent_{agentId}
- Embedding：配置 EMBEDDING_MODEL 走 OpenAI 兼容 /embeddings（缺省复用 LLM 地址，
  支持 Ollama bge-m3）；未配置时使用本地哈希 Mock 向量（确定性、无需外部服务）
- 维度一致性：模型返回维度 ≠ EMBEDDING_DIM 或集合维度不符时抛可读错误，
  提示按 scripts/rebuild_qdrant.py 重建集合
- 切分：chunk_size_tokens / chunk_overlap_tokens 可配（token ≈ 字符数 / 1.5）；
  PDF 按页注入「第 N 页」标记，长文档检索可追溯页码
- 数据库文件（第一期：SQLite + CSV，设计 v0.2）：结构化切片，按「表/行」为边界，
  payload 携带 table / rowStart / rowEnd / sourceType 元数据，杜绝单条记录被拦腰截断；
  SQLite 只读打开（mode=ro + query_only），绝不执行上传文件中的 SQL
"""
import csv
import hashlib
import logging
import math
import re
import sqlite3
import struct
import uuid
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_qdrant_client = None

# 数据库/表格类文件类型（结构化切片；其余按文本处理）
DATABASE_TYPES = {"db", "sqlite", "sqlite3", "csv"}
# 结构化来源类型映射：扩展名 → payload.sourceType
SOURCE_TYPE_MAP = {"db": "sqlite", "sqlite": "sqlite", "sqlite3": "sqlite"}


# ---------------- Qdrant ----------------

def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    try:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        _qdrant_client.get_collections()  # 触发连接校验
        return _qdrant_client
    except Exception as exc:  # noqa: BLE001
        logger.error("Qdrant 连接失败: %s", exc)
        raise RuntimeError("Qdrant 不可用") from exc


def _collection(agent_id: int) -> str:
    return f"agent_{agent_id}"


def _ensure_collection(client, agent_id: int) -> None:
    """确保集合存在且维度与配置一致；维度不符抛可读错误（集合创建后维度不可改）。"""
    name = _collection(agent_id)
    try:
        info = client.get_collection(name)
        dim = info.config.params.vectors.size
        if dim != settings.embedding_dim:
            raise RuntimeError(
                f"集合 {name} 维度 {dim} 与配置 EMBEDDING_DIM={settings.embedding_dim} 不一致，"
                "请运行 scripts/rebuild_qdrant.py 重建集合后重新入库")
    except RuntimeError:
        raise
    except Exception:  # noqa: BLE001 - collection 不存在则创建
        client.create_collection(
            collection_name=name,
            vectors_config={"size": settings.embedding_dim, "distance": "Cosine"},
        )
        logger.info("创建 Qdrant collection: %s (dim=%s)", name, settings.embedding_dim)


# ---------------- Embedding ----------------

def embed(text: str) -> list[float]:
    """文本向量化：配置了模型走 OpenAI 兼容 /embeddings，否则本地哈希 Mock 向量。"""
    if settings.embedding_model:
        return _embed_remote(text)
    logger.warning("未配置 EMBEDDING_MODEL，使用本地哈希 Mock 向量（检索质量有限，仅限开发）")
    return _embed_hash(text)


def _embed_remote(text: str) -> list[float]:
    base = (settings.embedding_base_url or settings.llm_base_url).rstrip("/")
    api_key = settings.embedding_api_key or settings.llm_api_key
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload = {"model": settings.embedding_model, "input": text}
    try:
        resp = httpx.post(f"{base}/embeddings", headers=headers, json=payload, timeout=30)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Embedding 服务不可用: {exc}") from exc
    if resp.status_code >= 400:
        detail = ""
        try:
            err = resp.json().get("error") if resp.headers.get("content-type", "").startswith("application/json") else None
            detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
        except ValueError:
            detail = resp.text[:200]
        raise RuntimeError(f"Embedding 请求失败（HTTP {resp.status_code}）：{detail}")
    try:
        vector = resp.json()["data"][0]["embedding"]
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"Embedding 返回格式异常: {exc}") from exc
    if len(vector) != settings.embedding_dim:
        raise RuntimeError(
            f"向量维度不一致：模型返回 {len(vector)} 维，配置 EMBEDDING_DIM={settings.embedding_dim}，"
            "请修改配置或运行 scripts/rebuild_qdrant.py 重建集合")
    return vector


def _embed_hash(text: str) -> list[float]:
    """确定性哈希向量（局部敏感）：未配置 Embedding 模型时的降级方案。"""
    dim = settings.embedding_dim
    vector = []
    for i in range(dim):
        digest = hashlib.sha256(f"{text}:{i}".encode("utf-8")).digest()
        value = struct.unpack("<f", digest[:4])[0] / 2_147_483_647.0
        if not math.isfinite(value):  # float32 可能解析出 NaN/Inf，JSON 非法，归零
            value = 0.0
        vector.append(value)
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


# ---------------- 解析与切分 ----------------

def parse_file(file_path: str) -> str:
    """按扩展名解析文档为纯文本（pdf/docx/txt/md）。

    PDF 按页提取并注入「第 N 页」标记，长文档检索可追溯页码。
    """
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"【第 {page_no} 页】\n{text}")
        return "\n\n".join(pages)
    if suffix == "docx":
        import docx
        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    if suffix in ("txt", "md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"不支持的文件类型: {suffix}")


# ---------------- 数据库解析与结构化切片（设计 v0.2 §7） ----------------

def _source_type(file_name: str) -> str:
    """由文件名推导来源类型：db/sqlite/sqlite3 → sqlite；csv → csv；其余按扩展名。"""
    suffix = Path(file_name).suffix.lower().lstrip(".")
    return SOURCE_TYPE_MAP.get(suffix, suffix)


def _resolve_db_config(slicing_mode: str, slicing_config: dict | None) -> dict:
    """解析并校验数据库类切片参数；自动模式返回系统默认值。

    slicingConfig（手动模式）支持：chunkRows / byTable / excludeTables /
    excludeColumns / keepHeader；非法参数抛可读错误（不入库）。
    """
    cfg = {"chunk_rows": settings.db_chunk_rows, "by_table": True,
           "exclude_tables": [], "exclude_columns": [], "keep_header": True}
    if slicing_mode != "manual" or not slicing_config:
        return cfg

    chunk_rows = slicing_config.get("chunkRows")
    if chunk_rows is not None:
        try:
            chunk_rows = int(chunk_rows)
        except (TypeError, ValueError):
            raise ValueError(f"每 chunk 行数必须为整数: {chunk_rows!r}") from None
        if not 1 <= chunk_rows <= settings.manual_max_chunk_rows:
            raise ValueError(f"每 chunk 行数需在 1-{settings.manual_max_chunk_rows} 之间")
        cfg["chunk_rows"] = chunk_rows
    if "byTable" in slicing_config:
        cfg["by_table"] = bool(slicing_config["byTable"])
    for key, target in (("excludeTables", "exclude_tables"),
                        ("excludeColumns", "exclude_columns")):
        vals = slicing_config.get(key)
        if vals is None:
            continue
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            raise ValueError(f"{key} 必须为字符串数组")
        cfg[target] = [v for v in vals if v.strip()]
    if "keepHeader" in slicing_config:
        cfg["keep_header"] = bool(slicing_config["keepHeader"])
    return cfg


def _resolve_text_config(slicing_config: dict | None) -> dict:
    """文本类手动切片参数：chunkSizeTokens / chunkOverlapTokens（缺省走默认值）。"""
    cfg = {"size_tokens": None, "overlap_tokens": None}
    if not slicing_config:
        return cfg

    size = slicing_config.get("chunkSizeTokens")
    if size is not None:
        try:
            size = int(size)
        except (TypeError, ValueError):
            raise ValueError(f"chunkSizeTokens 必须为整数: {size!r}") from None
        if not 1 <= size <= settings.manual_max_chunk_tokens:
            raise ValueError(f"chunkSizeTokens 需在 1-{settings.manual_max_chunk_tokens} 之间")
        cfg["size_tokens"] = size
    overlap = slicing_config.get("chunkOverlapTokens")
    if overlap is not None:
        try:
            overlap = int(overlap)
        except (TypeError, ValueError):
            raise ValueError(f"chunkOverlapTokens 必须为整数: {overlap!r}") from None
        if not 0 <= overlap <= settings.manual_max_chunk_tokens:
            raise ValueError(f"chunkOverlapTokens 需在 0-{settings.manual_max_chunk_tokens} 之间")
        cfg["overlap_tokens"] = overlap
    return cfg


def _quote_ident(name: str) -> str:
    """SQLite 标识符转义：双引号包裹并翻倍内部双引号（防注入，PRAGMA 不支持参数绑定）。"""
    return '"' + name.replace('"', '""') + '"'


def _iter_sqlite_rows(file_path: str):
    """只读打开 SQLite，逐表逐行产出 {table, headers, row_no, values}。

    - mode=ro 只读 URI + PRAGMA query_only=ON，绝不执行上传文件中的 SQL（安全 §11.2）
    - 大表游标 fetchmany 分批读取，防整表载入内存（性能 §11.1）
    - 表数超限直接报错，避免恶意文件拖垮服务
    """
    uri = Path(file_path).resolve().as_uri()
    conn = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=10)
    conn.execute("PRAGMA query_only = ON")
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name")]
        if len(tables) > settings.db_max_tables:
            raise ValueError(f"表数 {len(tables)} 超出上限 {settings.db_max_tables} 张")
        for table in tables:
            headers = [r[1] for r in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")]
            cur = conn.execute(f"SELECT * FROM {_quote_ident(table)}")
            row_no = 0
            while True:
                batch = cur.fetchmany(settings.db_batch_rows)
                if not batch:
                    break
                for values in batch:
                    row_no += 1
                    yield {"table": table, "headers": headers,
                           "row_no": row_no, "values": values}
    finally:
        conn.close()


def _read_csv_encoding(path: Path) -> str:
    """编码探测：UTF-8 优先（含 BOM），失败回退 GB18030（兼容中文 Excel 导出）。"""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return settings.csv_fallback_encoding


def _iter_csv_rows(file_path: str):
    """CSV：首行为表头，逐行产出 {table, headers, row_no, values}。"""
    path = Path(file_path)
    with path.open("r", encoding=_read_csv_encoding(path), newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return
        headers = [h.strip() for h in header]
        row_no = 0
        for row in reader:
            row_no += 1
            yield {"table": "", "headers": headers, "row_no": row_no, "values": row}


def _cell_text(value) -> str:
    """单元格转文本：None → 空串；二进制 → 可读截断；其余直接字符串化。"""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return repr(bytes(value))[:100]
    return str(value)


def _format_db_row(table: str, headers: list[str], row_no: int, values) -> str:
    """单行格式化为「表 <表名>，第 N 行。列A: 值1；列B: 值2；...」。"""
    title = f"表 {table}，" if table else ""
    pairs = []
    for i, value in enumerate(values):
        name = headers[i] if i < len(headers) and headers[i] else f"列{i + 1}"
        text = _cell_text(value)
        pairs.append(f"{name}: {text}" if text else f"{name}: ")
    return f"{title}第 {row_no} 行。" + "；".join(pairs)


def chunk_database(file_path: str, source_type: str, *,
                   chunk_rows: int | None = None,
                   by_table: bool = True,
                   exclude_tables: list[str] | None = None,
                   exclude_columns: list[str] | None = None,
                   keep_header: bool = True,
                   max_rows: int | None = None) -> list[dict]:
    """结构化切片：按「表/行」边界，单条记录绝不截断。

    - 每 chunk_rows 行合并为一条 chunk（受 chunk_size_tokens 字符上限约束，按行边界截断）
    - by_table=True 时按表边界切分（换表即冲刷）；False 时跨表连续切分（行文本自带表名可追溯）
    - 单行文本超长 → 该行独立成 chunk（保证大字段记录完整）
    - 空表/空行跳过；总行数超限直接拒绝（可配置 db_max_rows）
    - 返回 [{content, table, rowStart, rowEnd, sourceType}]
    - max_rows 用于预览（手动切片只跑前 N 行，避免大文件全量解析）
    """
    chunk_rows = chunk_rows or settings.db_chunk_rows
    chunk_size = max(1, int(settings.chunk_size_tokens * 1.5))  # token → 字符上限
    iter_rows = _iter_sqlite_rows if source_type == "sqlite" else _iter_csv_rows
    excluded_tables = set(exclude_tables or [])
    excluded_columns = set(exclude_columns or [])

    chunks: list[dict] = []
    total_rows = 0
    current_lines: list[str] = []
    current_start = 0
    current_end = 0
    current_table = ""
    buffer_len = 0
    data_count = 0

    def flush() -> None:
        nonlocal current_lines, current_start, current_end, current_table, buffer_len, data_count
        if not current_lines:
            return
        chunks.append({
            "content": "\n".join(current_lines),
            "table": current_table,
            "rowStart": current_start,
            "rowEnd": current_end,
            "sourceType": source_type,
        })
        current_lines, current_start, current_end, current_table, buffer_len, data_count = \
            [], 0, 0, "", 0, 0

    for row in iter_rows(file_path):
        total_rows += 1
        if total_rows > settings.db_max_rows:
            raise ValueError(f"总行数 {total_rows} 超出上限 {settings.db_max_rows} 行")
        if max_rows is not None and total_rows > max_rows:
            break

        table = row["table"]
        if excluded_tables and table in excluded_tables:
            continue
        # 过滤排除列（按列名，找不到则跳过过滤）
        excl_idx = {i for i, h in enumerate(row["headers"]) if h in excluded_columns}
        values = [v for i, v in enumerate(row["values"]) if i not in excl_idx]
        headers = [h for i, h in enumerate(row["headers"]) if i not in excl_idx]
        # 空行跳过
        if not any(_cell_text(v) for v in values):
            continue

        # 换表：by_table=True 时先冲刷上一表剩余行；False 时跨表连续切分，
        # 并在新表首行前补一条表头说明（行文本自身已带「表 <表名>」前缀）
        if table != current_table:
            if by_table:
                flush()
            elif keep_header and headers and current_lines:
                # 已有内容时补新表表头；chunk 首行场景由下方统一初始化（含 rowStart）
                current_lines.append(f"{('表 ' + table + '，') if table else ''}表头：{', '.join(headers)}")
            current_table = table

        line = _format_db_row(table, headers, row["row_no"], values)
        # 单行超长 → 独立成 chunk（整行完整保留，不与其他行混切）
        if len(line) > chunk_size:
            flush()
            chunks.append({"content": line, "table": table,
                           "rowStart": row["row_no"], "rowEnd": row["row_no"],
                           "sourceType": source_type})
            continue
        # 行数达上限或合并下一行超字符上限 → 冲刷当前 chunk（行边界截断）
        if current_lines and (data_count >= chunk_rows
                              or buffer_len + len(line) + 1 > chunk_size):
            flush()
            current_table = table
        if not current_lines:
            current_start = row["row_no"]
            if keep_header and headers:
                prefix = f"{('表 ' + table + '，') if table else ''}表头：{', '.join(headers)}"
                current_lines.append(prefix)
        current_lines.append(line)
        buffer_len += len(line) + 1
        current_end = row["row_no"]
        data_count += 1
    flush()
    return chunks


def parse_database(file_path: str, source_type: str, *,
                   max_rows: int | None = None) -> dict:
    """只读解析数据库文件结构（手动切片预览用，不入库）。

    返回 {sourceType, totalRows, tableCount, tables: [{name, columns, rowCount}]}。
    """
    iter_rows = _iter_sqlite_rows if source_type == "sqlite" else _iter_csv_rows
    tables: dict[str, dict] = {}
    total_rows = 0
    for row in iter_rows(file_path):
        total_rows += 1
        if max_rows is not None and total_rows > max_rows:
            break
        name = row["table"] or "csv"
        info = tables.setdefault(name, {"name": name, "columns": [], "rowCount": 0})
        if not info["columns"]:
            info["columns"] = row["headers"]
        info["rowCount"] += 1
    return {"sourceType": source_type, "totalRows": total_rows,
            "tableCount": len(tables), "tables": list(tables.values())}


def chunk_text(text: str, *, size_tokens: int | None = None,
               overlap_tokens: int | None = None) -> list[str]:
    """按 token 数切分（chunk_size_tokens + chunk_overlap_tokens，token ≈ 字符数 / 1.5）。

    手动切片模式下可通过 size_tokens / overlap_tokens 覆盖默认值（slicingConfig）。
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    token_per_char = 1 / 1.5
    size = max(1, int((size_tokens or settings.chunk_size_tokens) / token_per_char))
    overlap = min(max(0, int((overlap_tokens if overlap_tokens is not None
                              else settings.chunk_overlap_tokens) / token_per_char)),
                  size // 2)
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


# ---------------- 对外操作 ----------------

def ingest(agent_id: int, file_name: str, file_path: str, *,
           slicing_mode: str = "auto", slicing_config: dict | None = None,
           progress_url: str | None = None, document_id: int | None = None) -> int:
    """文档入库：解析 → 切分 → 向量化 → upsert 到 agent_{agentId}。

    - 数据库类文件（sqlite/csv）走结构化切片，payload 携带 table/rowStart/rowEnd/sourceType
    - 同名文件重新入库时按「agentId:fileName:idx」幂等 upsert，旧向量自动覆盖
    - slicing_mode=manual 时按 slicingConfig 覆盖切片参数（先校验，非法即抛错不入库）
    - progress_url 提供时，分批 upsert 并回写进度（processedChunks/totalChunks）
    """
    client = _get_qdrant()
    _ensure_collection(client, agent_id)

    source_type = _source_type(file_name)
    if source_type in DATABASE_TYPES:
        cfg = _resolve_db_config(slicing_mode, slicing_config)
        chunks = chunk_database(file_path, source_type, chunk_rows=cfg["chunk_rows"],
                                by_table=cfg["by_table"],
                                exclude_tables=cfg["exclude_tables"],
                                exclude_columns=cfg["exclude_columns"],
                                keep_header=cfg["keep_header"])
    else:
        text = parse_file(file_path)
        cfg = _resolve_text_config(slicing_config if slicing_mode == "manual" else None)
        chunks = [{"content": c, "table": "", "rowStart": None, "rowEnd": None,
                   "sourceType": source_type}
                  for c in chunk_text(text, size_tokens=cfg["size_tokens"],
                                      overlap_tokens=cfg["overlap_tokens"])]
    if not chunks:
        raise ValueError("文档内容为空，无可入库片段")

    total = len(chunks)
    _report_progress(progress_url, document_id, total=total)

    points = []
    batch_size = 50  # 分批 upsert + 回写进度，避免单次请求过大
    for idx, chunk in enumerate(chunks):
        # Qdrant point ID 仅支持无符号整数或 UUID；UUID v5 确定性生成，
        # 同名文件重复入库命中相同 ID 幂等覆盖（与旧字符串 ID 语义一致）
        points.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"af:{agent_id}:{file_name}:{idx}")),
            "vector": embed(chunk["content"]),
            "payload": {"agentId": agent_id, "file": file_name, "chunkIndex": idx,
                        "content": chunk["content"],
                        "table": chunk.get("table", ""),
                        "rowStart": chunk.get("rowStart"),
                        "rowEnd": chunk.get("rowEnd"),
                        "sourceType": chunk.get("sourceType", source_type)},
        })
        if len(points) >= batch_size:
            client.upsert(collection_name=_collection(agent_id), points=points)
            _report_progress(progress_url, document_id, processed=idx + 1)
            points = []
    if points:
        client.upsert(collection_name=_collection(agent_id), points=points)
        _report_progress(progress_url, document_id, processed=total)
    logger.info("文档入库: agentId=%s, file=%s, sourceType=%s, chunks=%s",
                agent_id, file_name, source_type, total)
    return total


def _report_progress(progress_url: str | None, document_id: int | None, *,
                     status: str | None = None, chunk_count: int | None = None,
                     processed: int | None = None, total: int | None = None,
                     error: str | None = None) -> None:
    """向后端回写入库进度（可选；失败静默，不阻断入库主链路）。"""
    if not progress_url:
        return
    body = {"documentId": document_id, "status": status, "chunkCount": chunk_count,
            "processedChunks": processed, "totalChunks": total, "error": error}
    body = {k: v for k, v in body.items() if v is not None}
    try:
        # 后端内部接口 /file/{id}/progress 强制校验 X-Internal-Token，必须携带
        resp = httpx.post(progress_url, json=body, timeout=5,
                          headers={"X-Internal-Token": settings.internal_token})
        if resp.status_code >= 400:
            logger.warning("进度回写失败: HTTP %s", resp.status_code)
    except Exception as exc:  # noqa: BLE001 - 进度回写失败不影响入库
        logger.warning("进度回写异常（忽略）: %s", exc)


def search(agent_id: int, query: str, top_k: int = 4) -> list[dict]:
    """向量检索，返回 [{file, content, score, table, rowStart, rowEnd, sourceType}]；
    集合不存在视为空知识库。"""
    client = _get_qdrant()
    name = _collection(agent_id)
    try:
        client.get_collection(name)
    except Exception:  # noqa: BLE001 - collection 不存在视为无知识
        return []

    # qdrant-client >= 1.13 移除 search()，改用 query_points()
    res = client.query_points(collection_name=name, query=embed(query), limit=top_k)
    return [{"file": h.payload.get("file", ""), "content": h.payload.get("content", ""),
             "score": h.score,
             "table": h.payload.get("table") or "",
             "rowStart": h.payload.get("rowStart"),
             "rowEnd": h.payload.get("rowEnd"),
             "sourceType": h.payload.get("sourceType") or ""} for h in res.points]


def delete_file(agent_id: int, file_name: str) -> int:
    """删除某文档的全部向量点。"""
    client = _get_qdrant()
    name = _collection(agent_id)
    try:
        client.get_collection(name)
    except Exception:  # noqa: BLE001 - collection 不存在无需删除
        return 0
    # 注意：points_selector 必须传 Filter 对象（新版 qdrant-client 不接受原始 dict）
    from qdrant_client.http import models  # 懒加载，与 _get_qdrant 风格一致
    selector = models.Filter(must=[
        models.FieldCondition(key="agentId", match=models.MatchValue(value=agent_id)),
        models.FieldCondition(key="file", match=models.MatchValue(value=file_name)),
    ])
    result = client.delete(collection_name=name, points_selector=selector, wait=True)
    return getattr(result, "count", 0)


def health() -> bool:
    try:
        _get_qdrant()
        return True
    except Exception:  # noqa: BLE001
        return False
