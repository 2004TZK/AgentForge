"""Workflow v1 执行引擎（M3 轻量版）：流程定义 → LangGraph 编译 → 节点级执行日志。

节点类型（轻量版限定）：
- tool：调用注册表工具，params={"tool": 工具名, "payload": {参数模板}}
- llm：调用 LLM 生成文本，params={"prompt": 提示词模板, "model"?, "temperature"?}

变量模板：节点 params 中的字符串支持 {var} 替换 —— var 来自运行输入 input 或
前置节点的输出（以 node_key 引用），如 {"repo": "spring-projects/spring-boot"} 输出
被节点 "fetch_repo" 产出后，后续节点可用 {fetch_repo}。

执行语义：线性链（next_node 指向）；节点失败 → 运行标记 FAILED（节点日志含错误），
后续节点不再执行；LLM/工具失败均不抛未捕获异常。LangGraph 不可用时降级为手动循环。
"""
import logging
import re
import time
from typing import TypedDict

from app.core.config import settings
from app.services.llm import LLMClient, llm_client
from app.tools import registry as tool_registry
from app.utils import trim_text

logger = logging.getLogger(__name__)

# 流程节点数量上限（防定义失控）
MAX_NODES = 50
# 节点输出/日志内容截断长度
LOG_OUTPUT_MAX = 500

# 支持的工作流输入变量（模板引用 {var}；用户消息等来自 input）
ALLOWED_NODE_TYPES = ("llm", "tool")


class WorkflowState(TypedDict):
    """LangGraph 状态：变量空间 / 节点日志 / 最终输出。"""
    vars: dict
    logs: list[dict]
    output: str
    failed: bool
    error: str


def validate_definition(definition: dict) -> list[dict]:
    """校验流程定义并返回节点列表（含起点推导）；非法定义抛 ValueError。"""
    nodes = definition.get("nodes") or []
    if not nodes:
        raise ValueError("流程定义缺少节点")
    if len(nodes) > MAX_NODES:
        raise ValueError(f"节点数超过上限 {MAX_NODES}")
    by_key: dict[str, dict] = {}
    for node in nodes:
        key = node.get("nodeKey")
        if not key:
            raise ValueError("节点缺少 nodeKey")
        if key in by_key:
            raise ValueError(f"节点键重复: {key}")
        if node.get("type") not in ALLOWED_NODE_TYPES:
            raise ValueError(f"不支持的节点类型: {node.get('type')}（仅支持 {ALLOWED_NODE_TYPES}）")
        by_key[key] = node

    # 线性链校验：唯一起点（无入边）→ 沿 next 无环遍历，必须覆盖全部节点
    has_incoming = {n.get("next") for n in nodes} - {None}
    starts = [n for n in nodes if n.get("nodeKey") not in has_incoming]
    if len(starts) != 1:
        raise ValueError(f"流程必须恰好一个起点，当前 {len(starts)} 个")
    order: list[str] = []
    seen: set[str] = set()
    cursor = starts[0]["nodeKey"]
    while cursor:
        if cursor in seen:
            raise ValueError(f"流程存在循环引用: {cursor}")
        seen.add(cursor)
        order.append(cursor)
        node = by_key[cursor]
        cursor = node.get("next") or None
        if cursor is not None and cursor not in by_key:
            raise ValueError(f"next 指向不存在的节点: {cursor}")
    if len(order) != len(nodes):
        raise ValueError("流程存在未连接的孤立节点")
    return [by_key[k] for k in order]


def _render(template: str, variables: dict) -> str:
    """模板替换：{var} 引用 variables；缺省变量保留原文（便于定位问题）。"""
    def replace(match: re.Match) -> str:
        key = match.group(1)
        value = variables.get(key)
        return str(value) if value is not None else match.group(0)
    return re.sub(r"\{([\w.]+)\}", replace, template)


def _render_payload(payload: dict, variables: dict) -> dict:
    """递归渲染 payload 中的模板字符串。"""
    rendered = {}
    for key, value in payload.items():
        if isinstance(value, str):
            rendered[key] = _render(value, variables)
        elif isinstance(value, dict):
            rendered[key] = _render_payload(value, variables)
        else:
            rendered[key] = value
    return rendered


def _build_node_fn(node: dict):
    """构造单个节点的执行函数（返回新状态；失败标记 failed 并记录错误）。"""
    key = node["nodeKey"]
    node_type = node["type"]
    params = node.get("params") or {}

    def fn(state: WorkflowState) -> WorkflowState:
        started = time.monotonic()
        log: dict = {"node": key, "type": node_type, "status": "SUCCESS",
                     "output": "", "error": None, "durationMs": 0}
        try:
            if node_type == "llm":
                prompt = _render(str(params.get("prompt", "")), state["vars"])
                model = params.get("model") or settings.llm_model
                temperature = float(params.get("temperature", 0.7))
                messages = [
                    {"role": "system", "content": "你是工作流执行节点，根据提示词生成输出。"},
                    {"role": "user", "content": prompt},
                ]
                # 节点显式指定模型时用独立客户端（不改动模块级默认客户端，避免并发串扰）；
                # 未指定时沿用模块级 llm_client（默认模型，保持测试/旧调用兼容）
                client = llm_client if model == llm_client.model else LLMClient(model=model)
                output = client.chat(messages, temperature=temperature)
            else:  # tool
                tool_name = params.get("tool") or ""
                payload = _render_payload(params.get("payload") or {}, state["vars"])
                output = tool_registry.call_tool(tool_name, payload)
            log["durationMs"] = int((time.monotonic() - started) * 1000)
            log["output"] = str(output)[:LOG_OUTPUT_MAX]
            return {
                **state,
                "vars": {**state["vars"], key: str(output)},
                "logs": state["logs"] + [log],
                "output": str(output),
            }
        except Exception as exc:  # noqa: BLE001 - 节点失败转为 FAILED 日志，不抛异常
            logger.warning("工作流节点失败 %s: %s", key, exc)
            log["durationMs"] = int((time.monotonic() - started) * 1000)
            log["status"] = "FAILED"
            log["error"] = str(exc)[:500]
            return {**state, "logs": state["logs"] + [log],
                    "failed": True, "error": str(exc)[:500]}

    return fn


def _build_graph(nodes: list[dict]):
    """按线性链编译 LangGraph：每个节点执行后失败即终止。"""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowState)
    for node in nodes:
        graph.add_node(node["nodeKey"], _build_node_fn(node))
    graph.add_edge(START, nodes[0]["nodeKey"])
    for i, node in enumerate(nodes):
        nxt = node.get("next")
        if nxt:
            graph.add_conditional_edges(node["nodeKey"], _route, {True: END, False: nxt})
        else:
            graph.add_edge(node["nodeKey"], END)
    return graph.compile()


def _route(state: WorkflowState) -> bool:
    return state["failed"]


def _execute_manually(nodes: list[dict], state: WorkflowState) -> WorkflowState:
    """LangGraph 不可用时的降级执行（功能等价）。"""
    current: dict | None = nodes[0]
    while current is not None:
        state = _build_node_fn(current)(state)
        if state["failed"]:
            break
        nxt = current.get("next")
        current = next((n for n in nodes if n["nodeKey"] == nxt), None) if nxt else None
    return state


def execute_workflow(definition: dict, inputs: dict | None = None) -> dict:
    """执行工作流，返回 {"status", "output", "nodeLogs", "error"}。"""
    nodes = validate_definition(definition)
    state: WorkflowState = {
        "vars": dict(inputs or {}),
        "logs": [],
        "output": "",
        "failed": False,
        "error": "",
    }
    try:
        state = _build_graph(nodes).invoke(state)
    except Exception as exc:  # noqa: BLE001 - langgraph 版本/依赖异常时降级
        logger.warning("LangGraph 不可用，降级为手动执行: %s", exc)
        state = _execute_manually(nodes, state)
    output = state.get("output") or ""
    # 工作流报告硬上限：与星盘解读一致，按句子边界截断，防止超长输出
    output = trim_text(output, settings.llm_answer_max_chars)
    return {
        "status": "FAILED" if state["failed"] else "SUCCESS",
        "output": output,
        "nodeLogs": state["logs"],
        "error": state.get("error") or "",
    }
