"""健康检查：GET /health → {status, redis, qdrant}。"""
from fastapi import APIRouter

from app.services import memory, rag_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    redis_ok = memory.health()
    qdrant_ok = rag_service.health()
    return {
        "status": "ok" if (redis_ok and qdrant_ok) else "degraded",
        "redis": redis_ok,
        "qdrant": qdrant_ok,
    }
