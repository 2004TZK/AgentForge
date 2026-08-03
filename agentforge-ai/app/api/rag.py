"""RAG 接口：入库 / 检索 / 删除（均校验 X-Internal-Token）。"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_internal_token
from app.core.config import settings
from app.schemas.rag import (DeleteResponse, IngestRequest, IngestResponse,
                             SearchRequest, SearchResponse, SearchResult)
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(require_internal_token)])


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    """文档入库：原始文件须已存在于共享卷（后端落盘后调用）。"""
    file_path = (Path(settings.upload_dir) / request.filePath).resolve()
    upload_root = Path(settings.upload_dir).resolve()
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"文件不存在: {request.filePath}")
    if upload_root not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")
    try:
        chunk_count = rag_service.ingest(request.agentId, request.fileName, str(file_path))
        return IngestResponse(status="ok", chunkCount=chunk_count)
    except Exception as exc:  # noqa: BLE001 - 统一转为 500，后端据此标记 FAILED
        logger.error("RAG 入库失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"RAG 入库失败: {exc}") from exc


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """知识检索（调试/内部用）。"""
    try:
        chunks = rag_service.search(request.agentId, request.query, request.topK)
        return SearchResponse(chunks=[SearchResult(**c) for c in chunks])
    except Exception as exc:  # noqa: BLE001
        logger.error("RAG 检索失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"RAG 检索失败: {exc}") from exc


@router.delete("/file", response_model=DeleteResponse)
def delete_file(agentId: int, fileName: str) -> DeleteResponse:
    """删除某文档的全部向量点。"""
    try:
        deleted = rag_service.delete_file(agentId, fileName)
        return DeleteResponse(deletedCount=deleted)
    except Exception as exc:  # noqa: BLE001
        logger.error("RAG 删除失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"RAG 删除失败: {exc}") from exc
