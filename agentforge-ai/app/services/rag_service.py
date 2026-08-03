"""RAG 服务：解析 → 切分 → Embedding → Qdrant 检索。

- Qdrant collection 按智能体隔离：agent_{agentId}
- Embedding：配置 EMBEDDING_MODEL 走 OpenAI 兼容 /embeddings（缺省复用 LLM 地址，
  支持 Ollama bge-m3）；未配置时使用本地哈希 Mock 向量（确定性、无需外部服务）
- 维度一致性：模型返回维度 ≠ EMBEDDING_DIM 或集合维度不符时抛可读错误，
  提示按 scripts/rebuild_qdrant.py 重建集合
- 切分：chunk_size_tokens / chunk_overlap_tokens 可配（token ≈ 字符数 / 1.5）；
  PDF 按页注入「第 N 页」标记，长文档检索可追溯页码
"""
import hashlib
import logging
import math
import re
import struct
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_qdrant_client = None


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


def chunk_text(text: str) -> list[str]:
    """按 token 数切分（chunk_size_tokens + chunk_overlap_tokens，token ≈ 字符数 / 1.5）。"""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    token_per_char = 1 / 1.5
    size = max(1, int(settings.chunk_size_tokens / token_per_char))
    overlap = min(max(0, int(settings.chunk_overlap_tokens / token_per_char)), size // 2)
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


# ---------------- 对外操作 ----------------

def ingest(agent_id: int, file_name: str, file_path: str) -> int:
    """文档入库：解析 → 切分 → 向量化 → upsert 到 agent_{agentId}。

    同名文件重新入库时按「agentId:fileName:idx」幂等 upsert，旧向量自动覆盖。
    """
    client = _get_qdrant()
    _ensure_collection(client, agent_id)

    text = parse_file(file_path)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("文档内容为空，无可入库片段")

    points = []
    for idx, chunk in enumerate(chunks):
        points.append({
            "id": f"{agent_id}:{file_name}:{idx}",
            "vector": embed(chunk),
            "payload": {"agentId": agent_id, "file": file_name, "chunkIndex": idx,
                        "content": chunk},
        })
    client.upsert(collection_name=_collection(agent_id), points=points)
    logger.info("文档入库: agentId=%s, file=%s, chunks=%s", agent_id, file_name, len(chunks))
    return len(chunks)


def search(agent_id: int, query: str, top_k: int = 4) -> list[dict]:
    """向量检索，返回 [{file, content, score}]；集合不存在视为空知识库。"""
    client = _get_qdrant()
    name = _collection(agent_id)
    try:
        client.get_collection(name)
    except Exception:  # noqa: BLE001 - collection 不存在视为无知识
        return []

    hits = client.search(collection_name=name, query_vector=embed(query), limit=top_k)
    return [{"file": h.payload.get("file", ""), "content": h.payload.get("content", ""),
             "score": h.score} for h in hits]


def delete_file(agent_id: int, file_name: str) -> int:
    """删除某文档的全部向量点。"""
    client = _get_qdrant()
    name = _collection(agent_id)
    try:
        client.get_collection(name)
    except Exception:  # noqa: BLE001 - collection 不存在无需删除
        return 0
    result = client.delete(collection_name=name,
                           points_selector={"filter": {"must": [
                               {"key": "agentId", "match": {"value": agent_id}},
                               {"key": "file", "match": {"value": file_name}},
                           ]}})
    return getattr(result, "count", 0)


def health() -> bool:
    try:
        _get_qdrant()
        return True
    except Exception:  # noqa: BLE001
        return False
