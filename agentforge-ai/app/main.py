"""AgentForge AI Service 入口：FastAPI 应用、CORS、路由注册、生命周期。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, rag
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    llm_mode = "Mock（未配置 LLM_API_KEY）" if not settings.llm_api_key else settings.llm_model
    logger.info("%s 启动: LLM=%s, Qdrant=%s:%s, Redis=%s:%s",
                settings.app_name, llm_mode,
                settings.qdrant_host, settings.qdrant_port,
                settings.redis_host, settings.redis_port)
    yield
    logger.info("%s 关闭", settings.app_name)


app = FastAPI(
    title="AgentForge AI Service",
    description="对话 / RAG / 工具调用（内部服务，经 X-Internal-Token 鉴权）",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：内部服务，按需放开（生产由 Nginx 网关收敛外部流量）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(rag.router)
