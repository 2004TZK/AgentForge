"""RAG 服务：解析 → 切分 → Embedding → Qdrant 检索。

- Qdrant collection 按智能体隔离：agent_{agentId}
- Embedding：配置 EMBEDDING_MODEL 走 OpenAI 兼容 /embeddings；
  未配置时使用本地哈希 Mock 向量（确定性、无需外部服务）
- 切分：默认 500 token + 50 token 重叠（token ≈ 字符数 / 1.5，后续可配置化）
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
    name = _collection(agent_id)
    try:
        client.get_collection(name)
    except Exception:  # noqa: BLE001 - collection 不存在则创建
        client.create_collection(
            collection_name=name,
            vectors_config={"size": settings.embedding_dim, "distance": "Cosine"},
        )
        logger.info("创建 Qdrant collection: %s (dim=%s)", name, settings.embedding_dim)


# ---------------- Embedding ----------------

def embed(text: str) -> list[float]:
    """文本向量化：配置了模型走 HTTP 接口，否则本地哈希 Mock 向量。"""
    if settings.embedding_model:
        return _embed_remote(text)
    return _embed_hash(text)


def _embed_remote(text: str) -> list[float]:
    url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    payload = {"model": settings.embedding_model, "input": text}
    resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


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
    """按扩展名解析文档为纯文本（pdf/docx/txt/md）。"""
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == "docx":
        import docx
        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    if suffix in ("txt", "md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"不支持的文件类型: {suffix}")


def chunk_text(text: str) -> list[str]:
    """按 token 数切分（500 token + 50 重叠），token ≈ 字符数 / 1.5。"""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    token_per_char = 1 / 1.5
    size = max(1, int(settings.chunk_size_tokens / token_per_char))
    overlap = max(0, int(settings.chunk_overlap_tokens / token_per_char))
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


# ---------------- 对外操作 ----------------

def ingest(agent_id: int, file_name: str, file_path: str) -> int:
    """文档入库：解析 → 切分 → 向量化 → upsert 到 agent_{agentId}。"""
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
    """向量检索，返回 [{file, content, score}]。"""
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
