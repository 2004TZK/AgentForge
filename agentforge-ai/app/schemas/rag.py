"""RAG 接口的请求/响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """POST /rag/ingest 请求：文档入库（原始文件已在共享卷）。

    slicingMode=manual 时 slicingConfig 生效（后端已校验合法性，此处二次防御）；
    progressUrl / documentId 用于异步入库的进度回写（可选）。
    """
    agentId: int
    fileName: str
    filePath: str
    documentId: Optional[int] = None
    slicingMode: str = "auto"                 # auto / manual
    slicingConfig: Optional[dict] = None      # 手动切片参数快照（JSON）
    progressUrl: Optional[str] = None         # 进度回写地址（后端内部接口）


class IngestResponse(BaseModel):
    """POST /rag/ingest 响应。"""
    status: str                      # ok / failed
    chunkCount: int = 0


class PreviewRequest(BaseModel):
    """POST /rag/preview 请求：只读解析结构 + 按切片配置预览前若干 chunk（不入库）。"""
    fileName: str
    filePath: str
    slicingMode: str = "auto"
    slicingConfig: Optional[dict] = None
    maxRows: Optional[int] = None    # 预览行数上限（默认服务端配置）


class PreviewTable(BaseModel):
    """单张表/sheet 的结构信息。"""
    name: str
    columns: List[str] = Field(default_factory=list)
    rowCount: int = 0


class PreviewResponse(BaseModel):
    """POST /rag/preview 响应。"""
    sourceType: str
    totalRows: int = 0
    tableCount: int = 0
    tables: List[PreviewTable] = Field(default_factory=list)
    sampleChunks: List[dict] = Field(default_factory=list)   # 前若干个结构化 chunk


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
    table: Optional[str] = None       # 结构化来源：表名/sheet 名
    rowStart: Optional[int] = None    # 行号区间起点（结构化来源）
    rowEnd: Optional[int] = None      # 行号区间终点
    sourceType: Optional[str] = None  # sqlite / csv / pdf / docx / txt / md


class SearchResponse(BaseModel):
    """POST /rag/search 响应。"""
    chunks: List[SearchResult] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    """DELETE /rag/file 响应。"""
    deletedCount: int = 0
