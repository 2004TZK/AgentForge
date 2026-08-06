"""RAG 接口：入库 / 检索 / 删除 / 预览（均校验 X-Internal-Token）。"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_internal_token
from app.core.config import settings
from app.schemas.rag import (DeleteResponse, IngestRequest, IngestResponse,
                             PreviewRequest, PreviewResponse, SearchRequest,
                             SearchResponse, SearchResult)
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(require_internal_token)])


def _resolve_uploaded_path(file_path: str) -> Path:
    """校验文件路径在共享卷内并返回绝对路径（防目录穿越）。"""
    resolved = (Path(settings.upload_dir) / file_path).resolve()
    upload_root = Path(settings.upload_dir).resolve()
    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"文件不存在: {file_path}")
    if upload_root not in resolved.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")
    return resolved


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    """文档入库：原始文件须已存在于共享卷（后端落盘后调用）。"""
    file_path = _resolve_uploaded_path(request.filePath)
    try:
        chunk_count = rag_service.ingest(
            request.agentId, request.fileName, str(file_path),
            slicing_mode=request.slicingMode, slicing_config=request.slicingConfig,
            progress_url=request.progressUrl, document_id=request.documentId)
        return IngestResponse(status="ok", chunkCount=chunk_count)
    except ValueError as exc:
        # 切片参数非法 / 超限等业务性错误：明确报 400，后端据此标记 FAILED 并展示原因
        logger.warning("RAG 入库参数错误: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"RAG 入库失败: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - 统一转为 500，后端据此标记 FAILED
        logger.error("RAG 入库失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"RAG 入库失败: {exc}") from exc


@router.post("/preview", response_model=PreviewResponse)
def preview(request: PreviewRequest) -> PreviewResponse:
    """只读解析结构 + 按切片配置预览前若干 chunk（手动切片预览，不入库）。"""
    file_path = _resolve_uploaded_path(request.filePath)
    try:
        source_type = rag_service._source_type(request.fileName)  # noqa: SLF001 - 内部预览同模块
        max_rows = request.maxRows or settings.db_max_rows
        info = rag_service.parse_database(str(file_path), source_type, max_rows=max_rows)
        # 提供了 slicingConfig 即按手动参数校验（防御：前端漏传 mode 也拦截非法参数）
        effective_mode = "manual" if request.slicingConfig else request.slicingMode
        cfg = rag_service._resolve_db_config(effective_mode, request.slicingConfig)  # noqa: SLF001
        sample = rag_service.chunk_database(
            str(file_path), source_type, chunk_rows=cfg["chunk_rows"],
            by_table=cfg["by_table"],
            exclude_tables=cfg["exclude_tables"], exclude_columns=cfg["exclude_columns"],
            keep_header=cfg["keep_header"], max_rows=min(max_rows, 5000))
        return PreviewResponse(**info, sampleChunks=sample[:3])
    except ValueError as exc:
        logger.warning("RAG 预览参数错误: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"RAG 预览失败: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("RAG 预览失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"RAG 预览失败: {exc}") from exc


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
