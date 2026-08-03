"""对话接口：POST /agent/chat（Phase 3+ 增加 /agent/chat/stream SSE）。"""
import logging

from fastapi import APIRouter, Depends

from app.api.deps import require_internal_token
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import agent_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["chat"], dependencies=[Depends(require_internal_token)])


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
    )
    return ChatResponse(answer=result["answer"], sources=result["sources"],
                        toolCalls=result["toolCalls"])
