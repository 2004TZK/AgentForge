"""Agent Runtime：LangGraph 状态图编排对话。

Phase 2（本版）：线性链路 —— 组装 Prompt（系统提示词 + 历史 + RAG 上下文）
→ LLM 回答；工具调用记录经 Planner 规则触发（calculator/github）。
M1 新增：流式对话（/agent/chat/stream）复用同一前置链路，LLM 回答逐块输出。
Phase 4：演进为 planner → RAG/工具分支 → LLM → 输出的完整循环。

LangGraph 不可用时降级为直接执行节点函数（功能等价，保证服务可用）。
"""
import logging
import re
from typing import TypedDict

from app.core.config import settings
from app.services import planner, rag_service
from app.services.llm import llm_client
from app.tools import registry as tool_registry

logger = logging.getLogger(__name__)


class ChatState(TypedDict):
    """状态图节点间传递的状态。"""
    agent_id: int
    system_prompt: str
    messages: list           # [{"role": ..., "content": ...}]
    message: str
    temperature: float
    tools: list[str]
    answer: str
    tool_calls: list[str]
    sources: list[str]


def _call_llm_node(state: ChatState) -> ChatState:
    """LLM 节点：携带完整 Prompt 调用模型（Mock 模式自动降级）。"""
    answer = llm_client.chat(state["messages"], temperature=state["temperature"])
    return {**state, "answer": answer}


def _build_graph():
    """构建线性状态图：START → call_llm → END。"""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ChatState)
    graph.add_node("call_llm", _call_llm_node)
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
    return graph.compile()


def _invoke(state: ChatState) -> ChatState:
    try:
        app = _build_graph()
        return app.invoke(state)
    except Exception as exc:  # noqa: BLE001 - langgraph 版本/依赖异常时降级
        logger.warning("LangGraph 不可用，降级为直接调用: %s", exc)
        return _call_llm_node(state)


def prepare_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
                 system_prompt: str | None = None, tools: list[str] | None = None) -> tuple:
    """对话前置链路：规则工具执行 + 可选 RAG 检索，组装最终消息序列。

    返回 (messages, tool_calls, sources)；同步与流式两条路径共用。
    """
    tools = tools or []
    tool_calls: list[str] = []
    context_notes: list[str] = []
    sources: list[str] = []

    # 1. 工具执行（Phase 2 规则触发；失败不阻断主链路，仅记录）
    for tool_name in planner.decide_tools(message, tools):
        try:
            if tool_name == "calculator":
                result = tool_registry.call_tool(tool_name, {"expression": message})
            elif tool_name == "github":
                match = re.search(r"[\w-]+/[\w.-]+", message)
                result = tool_registry.call_tool(tool_name, {"repo": match.group(0)})
            else:
                continue
            tool_calls.append(f"{tool_name}: {result}")
            context_notes.append(f"工具 {tool_name} 结果: {result}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("工具调用失败 %s: %s", tool_name, exc)
            context_notes.append(f"工具 {tool_name} 调用失败: {exc}")

    # 2. RAG 检索注入（防御式：Qdrant/collection 不可用则跳过）
    try:
        chunks = rag_service.search(agent_id, message, settings.rag_top_k)
        if chunks:
            knowledge = "\n\n".join(f"[{c['file']}] {c['content']}" for c in chunks)
            context_notes.append(f"知识库检索结果:\n{knowledge}")
            sources = sorted({c["file"] for c in chunks})
    except Exception as exc:  # noqa: BLE001
        logger.info("RAG 检索跳过: %s", exc)

    # 3. 组装消息序列（系统提示词 + 历史 + 本轮 + 上下文）
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history or [])
    user_content = message
    if context_notes:
        user_content = f"{user_content}\n\n[附加上下文]\n" + "\n".join(context_notes)
    messages.append({"role": "user", "content": user_content})
    return messages, tool_calls, sources


def run_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
             system_prompt: str | None = None, model_name: str | None = None,
             temperature: float | None = 0.7, tools: list[str] | None = None) -> dict:
    """同步对话入口：返回 {answer, sources, toolCalls}。"""
    messages, tool_calls, sources = prepare_chat(
        agent_id=agent_id, message=message, history=history,
        system_prompt=system_prompt, tools=tools,
    )
    state: ChatState = {
        "agent_id": agent_id,
        "system_prompt": system_prompt or "",
        "messages": messages,
        "message": message,
        "temperature": temperature if temperature is not None else 0.7,
        "tools": tools or [],
        "answer": "",
        "tool_calls": tool_calls,
        "sources": sources,
    }
    result = _invoke(state)
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", sources),
        "toolCalls": result.get("tool_calls", tool_calls),
    }


async def stream_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
                      system_prompt: str | None = None, model_name: str | None = None,
                      temperature: float | None = 0.7, tools: list[str] | None = None):
    """流式对话入口：复用前置链路，逐块产出事件字典。

    事件：{"type": "delta", "content": ...}（逐块）/
         {"type": "done", "answer": 完整回答, "sources": [...], "toolCalls": [...]}（末尾）。

    M1 流式路径直连 LLM 流式接口（状态图当前为线性链，功能等价）；
    Phase 4 接入图节点时保持事件协议不变。
    """
    messages, tool_calls, sources = prepare_chat(
        agent_id=agent_id, message=message, history=history,
        system_prompt=system_prompt, tools=tools,
    )
    full = ""
    async for delta in llm_client.chat_stream(
            messages, temperature=temperature if temperature is not None else 0.7):
        full += delta
        yield {"type": "delta", "content": delta}
    yield {"type": "done", "answer": full, "sources": sources, "toolCalls": tool_calls}
