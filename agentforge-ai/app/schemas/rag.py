"""RAG 接口的请求/响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """POST /rag/ingest 请求：文档入库（原始文件已在共享卷）。"""
    agentId: int
    fileName: str
    filePath: str


class IngestResponse(BaseModel):
    """POST /rag/ingest 响应。"""
    status: str                      # ok / failed
    chunkCount: int = 0


class SearchRequest(BaseModel):
    """POST /rag/search 请求（调试/内部用）。"""
    agentId: int
    query: str
    topK: int = 4


class SearchResult(BaseModel):
    """单条检索结果。"""
    file: str
    content: str
    score: float = 0.0


class SearchResponse(BaseModel):
    """POST /rag/search 响应。"""
    chunks: List[SearchResult] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    """DELETE /rag/file 响应。"""
    deletedCount: int = 0
