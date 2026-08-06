"""Agent Runtime：LangGraph 状态图编排对话。

M3（Phase 4）：从线性链进化为 ReAct 工具循环 ——
  ① LLM 依据工具 Schema 自主决策（OpenAI 兼容 tools 参数，本地模型与 think 并存）
  ② 多轮循环：工具执行 → 结果回填 → 继续调用，最多 MAX_TOOL_ROUNDS 轮
  ③ 规则触发（planner 关键字启发式）保留为兜底：LLM 未决策工具时生效
  ④ RAG 检索上下文（M2）与 Redis 短期记忆（M3，按用户隔离）注入
工具失败不阻断主链路：执行异常转为失败说明回填给 LLM，继续总结。
LangGraph 不可用时降级为直接执行节点函数（功能等价，保证服务可用）。
"""
import json
import logging
import re
from typing import TypedDict

from app.core.config import settings
from app.services import memory, planner, rag_service
from app.services.llm import LLMClient, llm_client
from app.tools import registry as tool_registry

logger = logging.getLogger(__name__)

# ReAct 循环最大工具执行轮数（防死循环；同步与流式共用）
MAX_TOOL_ROUNDS = 3


class ChatState(TypedDict):
    """状态图节点间传递的状态。"""
    agent_id: int
    user_id: int | None
    provider: dict | None          # M4：请求级模型 Provider 覆盖 {type, baseUrl, apiKey}
    system_prompt: str
    messages: list           # [{"role": ..., "content": ...}]
    message: str
    temperature: float
    tools: list[str]
    tool_schemas: list[dict]         # OpenAI function 格式（供 LLM 决策）
    tool_configs: dict               # {tool_name: config}（智能体工具配置）
    max_rounds: int
    round: int                       # 已执行工具轮数
    answer: str
    tool_calls: list[dict]           # [{"name", "arguments", "result"}]
    sources: list[dict]              # [{file, snippet, score}]
    pending_tool_calls: list[dict]   # 本轮 LLM 决策待执行的工具调用
    llm_content: str                 # 最近一次 LLM 输出文本


# ---------------- ReAct 图节点 ----------------

def _client(state: ChatState) -> LLMClient:
    """请求级 Provider 覆盖（M4）：Agent 绑定 Provider 时按其 base_url/api_key 调用，
    否则回落模块级默认客户端（环境变量配置）。"""
    provider = state.get("provider")
    return llm_client if not provider else LLMClient(provider)


def _call_llm_node(state: ChatState) -> ChatState:
    """LLM 节点：携带工具 Schema 决策（无工具时退化为普通回答）。"""
    client = _client(state)
    if not state["tool_schemas"]:
        content = client.chat(state["messages"], temperature=state["temperature"])
        return {**state, "llm_content": content, "pending_tool_calls": []}
    result = client.chat_with_tools(state["messages"], state["tool_schemas"],
                                    temperature=state["temperature"])
    return {**state, "llm_content": result["content"],
            "pending_tool_calls": result["tool_calls"]}


def _route_after_llm(state: ChatState) -> str:
    """路由：有待执行工具且未达轮数上限 → 执行工具；否则结束。"""
    if state["pending_tool_calls"] and state["round"] < state["max_rounds"]:
        return "execute_tool"
    return "end"


def _execute_tool_node(state: ChatState) -> ChatState:
    """工具执行节点：回填 assistant 工具调用消息与 tool 结果消息，推进轮数。"""
    messages = list(state["messages"])
    tool_calls = list(state["tool_calls"])
    pending = state["pending_tool_calls"]
    messages.append(_assistant_tool_message(state["llm_content"], pending))
    for call in pending:
        name = call["name"]
        args = call["arguments"] or {}
        result = _safe_call_tool(name, args, state["tool_configs"].get(name))
        tool_msg: dict = {"role": "tool", "content": result}
        if call.get("tool_call_id"):  # OpenAI 兼容协议需 tool_call_id；Ollama 原生用 name
            tool_msg["tool_call_id"] = call["tool_call_id"]
        else:
            tool_msg["name"] = name
        messages.append(tool_msg)
        tool_calls.append({"name": name, "arguments": args, "result": result})
    return {**state, "messages": messages, "round": state["round"] + 1,
            "tool_calls": tool_calls}


def _build_react_graph():
    """构建 ReAct 状态图：START → call_llm → (execute_tool → call_llm)* → END。"""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ChatState)
    graph.add_node("call_llm", _call_llm_node)
    graph.add_node("execute_tool", _execute_tool_node)
    graph.add_edge(START, "call_llm")
    graph.add_conditional_edges("call_llm", _route_after_llm,
                                {"execute_tool": "execute_tool", "end": END})
    graph.add_edge("execute_tool", "call_llm")
    return graph.compile()


def _react_loop(state: ChatState) -> ChatState:
    """执行 ReAct 循环；LangGraph 不可用时降级为手动循环（功能等价）。"""
    try:
        return _build_react_graph().invoke(state)
    except Exception as exc:  # noqa: BLE001 - langgraph 版本/依赖异常时降级
        logger.warning("LangGraph 不可用，降级为直接执行: %s", exc)
        state = _call_llm_node(state)
        while _route_after_llm(state) == "execute_tool":
            state = _execute_tool_node(state)
            state = _call_llm_node(state)
        return state


# ---------------- 规则触发兜底（Phase 2 行为保留） ----------------

def _rule_payload(tool_name: str, message: str) -> dict:
    """从用户消息提取规则触发的工具参数（与 Phase 2 关键字启发式一致）。"""
    if tool_name == "calculator":
        return {"expression": message}
    if tool_name == "github":
        match = re.search(r"[\w-]+/[\w.-]+", message)
        if not match:
            raise ValueError("未识别到仓库路径")
        return {"repo": match.group(0)}
    raise ValueError(f"规则触发暂不支持工具 {tool_name}")


def _rule_fallback(state: ChatState) -> ChatState:
    """规则兜底：LLM 未产生工具调用时，按关键字启发式执行工具并回填上下文后重新总结。

    返回更新后的 state（answer 为重新总结结果；无规则命中时原样返回）。
    """
    rule_tools = planner.decide_tools(state["message"], state["tools"])
    if not rule_tools or state["tool_calls"]:
        return state
    notes: list[str] = []
    for name in rule_tools:
        try:
            payload = _rule_payload(name, state["message"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("规则触发参数提取失败 %s: %s", name, exc)
            continue
        result = _safe_call_tool(name, payload, state["tool_configs"].get(name))
        notes.append(f"工具 {name} 结果: {result}")
        state["tool_calls"].append({"name": name, "arguments": payload, "result": result})
    if not notes:
        return state
    messages = list(state["messages"])
    last = dict(messages[-1])
    last["content"] = f"{last['content']}\n\n[附加上下文]\n" + "\n".join(notes)
    messages[-1] = last
    state["messages"] = messages
    state["answer"] = _client(state).chat(messages, temperature=state["temperature"])
    return state


# ---------------- 消息组装 ----------------

def prepare_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
                 system_prompt: str | None = None, tools: list[str] | None = None,
                 user_id: int | None = None) -> tuple:
    """对话前置链路：RAG 检索 + 短期记忆注入，组装最终消息序列。

    返回 (messages, tool_calls, sources)；同步与流式两条路径共用。
    M3 起工具执行移至 ReAct 循环/兜底阶段，此处 tool_calls 恒为空（协议兼容）。
    sources 为 [{file, snippet, score}]；空知识库（无集合/无命中/检索异常）自动降级普通对话。
    """
    context_notes: list[str] = []
    sources: list[dict] = []

    # 1. RAG 检索注入（防御式：Qdrant/collection 不可用则跳过，降级普通对话）
    try:
        chunks = rag_service.search(agent_id, message, settings.rag_top_k)
        if chunks:
            knowledge = "\n\n".join(f"[{c['file']}] {c['content']}" for c in chunks)
            context_notes.append(f"知识库检索结果:\n{knowledge}")
            sources = [{"file": c["file"], "snippet": c["content"][:200], "score": c["score"],
                        "table": c.get("table") or "", "rowStart": c.get("rowStart"),
                        "rowEnd": c.get("rowEnd"), "sourceType": c.get("sourceType") or ""}
                       for c in chunks]
    except Exception as exc:  # noqa: BLE001
        logger.info("RAG 检索跳过（降级普通对话）: %s", exc)

    # 2. 短期记忆注入（M3：跨会话/设备回忆；按用户隔离，与 MySQL 历史去重）
    memory_note = _memory_note(agent_id, user_id, history)

    # 3. 组装消息序列（系统提示词 + 历史 + 本轮 + 上下文）
    messages: list[dict] = []
    sys_text = (system_prompt or "").strip()
    if memory_note:
        sys_text = f"{sys_text}\n\n[近期记忆（其他会话）]\n{memory_note}".strip()
    if sys_text:
        messages.append({"role": "system", "content": sys_text})
    messages.extend(history or [])
    user_content = message
    if context_notes:
        user_content = f"{user_content}\n\n[附加上下文]\n" + "\n".join(context_notes)
    messages.append({"role": "user", "content": user_content})
    return messages, [], sources


def _memory_note(agent_id: int, user_id: int | None, history: list[dict] | None) -> str:
    """读取短期记忆并过滤与当前历史重复的条目，返回可读文本（无则空串）。"""
    if user_id is None:
        return ""
    try:
        memory_msgs = memory.get_history(agent_id, user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取记忆失败（降级）: %s", exc)
        return ""
    if not memory_msgs:
        return ""
    history_contents = {m.get("content") for m in (history or [])}
    fresh = [m for m in memory_msgs
             if m.get("role") in ("user", "assistant") and m.get("content")
             and m["content"] not in history_contents]
    if not fresh:
        return ""
    lines = [f"- {m['role']}: {m['content'][:200]}" for m in fresh[-6:]]
    return "\n".join(lines)


def _assistant_tool_message(content: str, pending: list[dict]) -> dict:
    """构造携带 tool_calls 的 assistant 消息（协议要求：其后必须跟 tool 结果消息）。

    OpenAI 兼容格式带 id + type=function（远端）；Ollama 原生仅 function（本地）。
    """
    msg: dict = {"role": "assistant", "content": content or ""}
    if pending:
        calls = []
        for call in pending:
            fn = {"name": call["name"], "arguments": call["arguments"]}
            if call.get("tool_call_id"):
                calls.append({"id": call["tool_call_id"], "type": "function", "function": fn})
            else:
                calls.append({"function": fn})
        msg["tool_calls"] = calls
    return msg


def _safe_call_tool(name: str, args: dict, config: dict | None = None) -> str:
    """工具调用兜底：任何异常转为失败说明文本回填（不阻断主链路）。"""
    try:
        return tool_registry.call_tool(name, args, config)
    except Exception as exc:  # noqa: BLE001 - 工具失败不影响对话主链路
        logger.warning("工具调用失败 %s: %s", name, exc)
        return f"[工具 {name} 调用失败: {exc}]"


def _format_tool_calls(tool_calls: list[dict]) -> list[str]:
    """工具调用记录 → 展示用字符串列表（协议兼容 M2 的 List<String>）。"""
    return [f"{c['name']}({json.dumps(c['arguments'], ensure_ascii=False)}) → {c['result'][:200]}"
            for c in tool_calls]


# ---------------- 对话入口 ----------------

def run_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
             system_prompt: str | None = None, model_name: str | None = None,
             temperature: float | None = 0.7, tools: list[str] | None = None,
             user_id: int | None = None, tool_configs: dict | None = None,
             provider: dict | None = None) -> dict:
    """同步对话入口：ReAct 工具循环 → 规则兜底 → 记忆写入，返回 {answer, sources, toolCalls}。"""
    messages, _, sources = prepare_chat(
        agent_id=agent_id, message=message, history=history,
        system_prompt=system_prompt, tools=tools, user_id=user_id,
    )
    state: ChatState = {
        "agent_id": agent_id,
        "user_id": user_id,
        "provider": provider,
        "system_prompt": system_prompt or "",
        "messages": messages,
        "message": message,
        "temperature": temperature if temperature is not None else 0.7,
        "tools": tools or [],
        "tool_schemas": tool_registry.openai_tools(tools or []),
        "tool_configs": tool_configs or {},
        "max_rounds": MAX_TOOL_ROUNDS,
        "round": 0,
        "answer": "",
        "tool_calls": [],
        "sources": sources,
        "pending_tool_calls": [],
        "llm_content": "",
    }
    result = _react_loop(state)
    if not result.get("answer"):
        result["answer"] = result.get("llm_content") or ""
    # LLM 未决策工具但规则命中 → 兜底执行并重新总结（保证工具链路可用）
    if not result["tool_calls"]:
        result = _rule_fallback(result)
    # 防呆：工具轮次耗尽后 LLM 仍无文本输出 → 不带工具强制总结一次
    if not result["answer"]:
        result["answer"] = _client(result).chat(result["messages"],
                                                temperature=result["temperature"])

    answer = result["answer"]
    if user_id is not None and answer:
        memory.append_round(agent_id, user_id, message, answer)
    return {
        "answer": answer,
        "sources": result.get("sources", sources),
        "toolCalls": _format_tool_calls(result["tool_calls"]),
    }


async def stream_chat(*, agent_id: int, message: str, history: list[dict] | None = None,
                      system_prompt: str | None = None, model_name: str | None = None,
                      temperature: float | None = 0.7, tools: list[str] | None = None,
                      user_id: int | None = None, tool_configs: dict | None = None,
                      provider: dict | None = None):
    """流式对话入口：ReAct 循环流式执行，产出事件字典。

    事件：{"type": "delta", "content"}（逐块）/
         {"type": "tool", "name", "arguments", "result"}（工具执行）/
         {"type": "done", "answer", "sources", "toolCalls"}（末尾）。
    工具轮通常无内容增量（模型直接输出 tool_calls）；文本轮增量照常输出。
    """
    messages, _, sources = prepare_chat(
        agent_id=agent_id, message=message, history=history,
        system_prompt=system_prompt, tools=tools, user_id=user_id,
    )
    tool_schemas = tool_registry.openai_tools(tools or [])
    tool_calls: list[dict] = []
    temp = temperature if temperature is not None else 0.7
    full = ""
    client = LLMClient(provider) if provider else llm_client

    # ReAct 流式循环：前 MAX_TOOL_ROUNDS 轮带工具，之后强制无工具总结（保证终止）
    round_no = 0
    while True:
        with_tools = bool(tool_schemas) and round_no < MAX_TOOL_ROUNDS
        holder = {"content": "", "tool_calls": []}
        async for event in _llm_round(client, messages, with_tools, tool_schemas, temp, holder):
            if event["type"] == "delta":
                full += event["content"]
                yield {"type": "delta", "content": event["content"]}
        pending = holder["tool_calls"]
        if not pending:
            break
        messages.append(_assistant_tool_message(holder["content"], pending))
        for call in pending:
            name = call["name"]
            args = call["arguments"] or {}
            result = _safe_call_tool(name, args, (tool_configs or {}).get(name))
            tool_msg: dict = {"role": "tool", "content": result}
            if call.get("tool_call_id"):
                tool_msg["tool_call_id"] = call["tool_call_id"]
            else:
                tool_msg["name"] = name
            messages.append(tool_msg)
            tool_calls.append({"name": name, "arguments": args, "result": result})
            yield {"type": "tool", "name": name, "arguments": args, "result": result}
        round_no += 1

    # 规则兜底：LLM 未调用工具且未输出任何内容（工具决策失败）时按关键字启发式执行
    if not tool_calls and not full.strip():
        fallback_notes: list[str] = []
        for name in planner.decide_tools(message, tools or []):
            try:
                payload = _rule_payload(name, message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("规则触发参数提取失败 %s: %s", name, exc)
                continue
            result = _safe_call_tool(name, payload, (tool_configs or {}).get(name))
            fallback_notes.append(f"工具 {name} 结果: {result}")
            tool_calls.append({"name": name, "arguments": payload, "result": result})
            yield {"type": "tool", "name": name, "arguments": payload, "result": result}
        if fallback_notes:
            last = dict(messages[-1])
            last["content"] = f"{last['content']}\n\n[附加上下文]\n" + "\n".join(fallback_notes)
            messages[-1] = last
            async for delta in client.chat_stream(messages, temperature=temp):
                full += delta
                yield {"type": "delta", "content": delta}

    if user_id is not None and full:
        memory.append_round(agent_id, user_id, message, full)
    yield {"type": "done", "answer": full, "sources": sources,
           "toolCalls": _format_tool_calls(tool_calls)}


async def _llm_round(client: LLMClient, messages: list[dict], with_tools: bool,
                     tool_schemas: list[dict], temperature: float, holder: dict):
    """一轮 LLM 调用：产出 delta 事件；结束后将 {content, tool_calls} 写入 holder。"""
    content = ""
    pending: list[dict] = []
    if with_tools:
        async for event in client.chat_stream_with_tools(messages, tool_schemas, temperature):
            if event["type"] == "delta":
                content += event["content"]
                yield event
            else:  # done（工具轮结束，LLM 内部汇总事件不透传客户端）
                pending = event["tool_calls"]
    else:
        async for delta in client.chat_stream(messages, temperature):
            content += delta
            yield {"type": "delta", "content": delta}
    holder["content"] = content
    holder["tool_calls"] = pending
