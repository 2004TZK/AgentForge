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


class SourceItem(BaseModel):
    """回答引用的知识库来源（M2 起为对象，含可查看的片段）。"""
    file: str
    snippet: str = Field(description="引用片段（截断）")
    score: float = 0.0


class ChatResponse(BaseModel):
    """POST /agent/chat 响应。"""
    answer: str
    sources: List[SourceItem] = []
    toolCalls: List[str] = []
