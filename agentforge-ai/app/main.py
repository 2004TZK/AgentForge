"""AgentForge AI Service 入口：FastAPI 应用、CORS、路由注册、生命周期。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, health, rag, star_report, tools, workflow
from app.core.config import settings
from app.core.errors import AiServiceError
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
app.include_router(tools.router)
app.include_router(workflow.router)
app.include_router(star_report.router)


@app.exception_handler(AiServiceError)
async def handle_ai_service_error(_request: Request, exc: AiServiceError) -> JSONResponse:
    """结构化错误响应：同步接口统一返回 {"code", "message"}（与后端 ResultCode 对齐）。

    流式接口不经过此处 —— 错误在事件生成器内转为 SSE error 事件。
    """
    logger.error("AI 服务错误 code=%s: %s", exc.code, exc)
    return JSONResponse(status_code=exc.http_status,
                        content={"code": exc.code, "message": str(exc)})
