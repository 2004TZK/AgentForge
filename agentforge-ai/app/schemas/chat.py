"""对话接口的请求/响应模型（与后端 ai-gateway 的 AiChatRequest/AiChatResponse 对齐）。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    """单条历史消息。"""
    role: str = Field(description="user / assistant")
    content: str = Field(description="消息内容")


class ChatRequest(BaseModel):
    """POST /agent/chat 请求。"""
    agentId: int
    message: str
    history: List[ChatHistoryItem] = Field(default_factory=list)
    # Agent 配置快照（由后端从 MySQL 加载透传，本服务不直连 MySQL）
    systemPrompt: Optional[str] = None
    modelName: Optional[str] = None
    temperature: Optional[float] = None
    tools: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """POST /agent/chat 响应。"""
    answer: str
    sources: List[str] = []
    toolCalls: List[str] = []
