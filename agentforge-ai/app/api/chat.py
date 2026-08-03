"""对话接口：POST /agent/chat（同步）、POST /agent/chat/stream（SSE 流式）。"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import require_internal_token
from app.core.config import settings
from app.core.errors import AiServiceError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import agent_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["chat"], dependencies=[Depends(require_internal_token)])

# SSE 响应头：禁用缓存与代理缓冲，保证逐字透传（Nginx 读 X-Accel-Buffering 关闭缓冲）
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [{"role": h.role, "content": h.content} for h in request.history]
    result = agent_runtime.run_chat(
        agent_id=request.agentId,
        message=request.message,
        history=history,
        system_prompt=request.systemPrompt,
        model_name=request.modelName,
        temperature=request.temperature,
        tools=request.tools,
        user_id=request.userId,
        tool_configs=request.toolConfigs,
        provider=request.provider,
    )
    return ChatResponse(answer=result["answer"], sources=result["sources"],
                        toolCalls=result["toolCalls"])


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """SSE 流式对话：delta 增量 + done 汇总（含完整答案供后端落库）+ error 事件。"""
    return StreamingResponse(
        _sse_events(request),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _sse_events(request: ChatRequest):
    """事件生成器：长时间无事件时发送保活注释帧；错误统一转为 error 事件。

    实现说明：LLM 流在独立 pump 任务中消费，避免对进行中的 IO 取消失效，
    保活帧只影响网关/代理侧空闲超时，不影响模型流本身。
    """
    history = [{"role": h.role, "content": h.content} for h in request.history]
    gen = agent_runtime.stream_chat(
        agent_id=request.agentId,
        message=request.message,
        history=history,
        system_prompt=request.systemPrompt,
        model_name=request.modelName,
        temperature=request.temperature,
        tools=request.tools,
        user_id=request.userId,
        tool_configs=request.toolConfigs,
        provider=request.provider,
    )
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def pump() -> None:
        """消费流式事件；异常转 error 事件，正常结束投递 None 哨兵。"""
        try:
            async for event in gen:
                await queue.put(event)
        except AiServiceError as exc:
            logger.error("流式对话失败 code=%s: %s", exc.code, exc)
            await queue.put({"type": "error", "code": exc.code, "message": str(exc)})
        except Exception:  # noqa: BLE001 - 兜底不泄露内部细节
            logger.exception("流式对话未知异常")
            await queue.put({"type": "error", "code": 50000, "message": "对话服务内部错误"})
        finally:
            await queue.put(None)

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=settings.sse_ping_interval_seconds)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            if event is None:
                return
            yield _sse_frame(event)
            if event.get("type") in ("done", "error"):
                return
    finally:
        pump_task.cancel()


def _sse_frame(event: dict) -> str:
    """序列化为单行 data 事件（ensure_ascii=False 保持中文可读）。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
