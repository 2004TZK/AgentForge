"""工具注册表：name → {call, schema}。新增工具只需注册即可被 LLM/Workflow 使用。

- schema 结构：{"name", "description", "parameters": {参数名: {type, description, required?}},
  "config": {配置参数名: {type, description}}} —— config 为智能体级配置（存 agent_tool.tool_config，
  前端按 Schema 渲染配置表单），不进 LLM 工具参数
- call(payload, config)：payload 为 LLM 工具调用参数；config 为智能体工具配置
- M3 起支持 OpenAI 兼容 tools 参数格式（type=function），供 Ollama 原生 API / OpenAI 兼容接口使用
"""
from app.tools import calculator, current_time, github, star_chart, web_search


def _calc(payload: dict, config: dict | None = None) -> str:
    return str(calculator.evaluate(payload.get("expression", "")))


def _github(payload: dict, config: dict | None = None) -> str:
    import json
    return json.dumps(github.query_repo(payload.get("repo", ""), config), ensure_ascii=False)


def _current_time(payload: dict, config: dict | None = None) -> str:
    return current_time.current_time(payload.get("time_format", "") or "%Y-%m-%d %H:%M:%S")


def _web_search(payload: dict, config: dict | None = None) -> str:
    import json
    return json.dumps(web_search.web_search(payload.get("query", ""), config), ensure_ascii=False)


def _star_chart(payload: dict, config: dict | None = None) -> str:
    return star_chart.run(payload, config)


TOOL_REGISTRY = {
    "calculator": {"call": _calc, "schema": calculator.SCHEMA},
    "github": {"call": _github, "schema": github.SCHEMA},
    "current_time": {"call": _current_time, "schema": current_time.SCHEMA},
    "web_search": {"call": _web_search, "schema": web_search.SCHEMA},
    # star_chart 出参为完整排盘 JSON（数 KB），禁用结果截断，保证 LLM 拿到全量数据
    "star_chart": {"call": _star_chart, "schema": star_chart.SCHEMA, "result_max": None},
}

# 工具执行结果的展示截断长度（防超长结果污染对话/日志）
RESULT_MAX = 500


def is_registered(tool_name: str) -> bool:
    return tool_name in TOOL_REGISTRY


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())


def list_tool_meta() -> list[dict]:
    """全部工具的元数据（供后端透传、前端按 Schema 渲染配置表单）。"""
    return [
        {
            "name": s["name"],
            "description": s.get("description", ""),
            "parameters": s.get("parameters", {}),
            "config": s.get("config", {}),
        }
        for s in (TOOL_REGISTRY[n]["schema"] for n in sorted(TOOL_REGISTRY))
    ]


def openai_tools(tool_names: list[str]) -> list[dict]:
    """将工具名列表转换为 OpenAI/Ollama 兼容的 tools 参数格式。"""
    return [to_openai_tool(name) for name in tool_names if name in TOOL_REGISTRY]


def to_openai_tool(tool_name: str) -> dict:
    """单个工具 → OpenAI function 格式（type=function）。

    注册表 schema 的 parameters 为扁平参数描述，转换为
    {"type": "object", "properties": {...}, "required": [...]} 的标准结构。
    """
    schema = TOOL_REGISTRY[tool_name]["schema"]
    properties: dict = {}
    required: list[str] = []
    for param, spec in schema.get("parameters", {}).items():
        properties[param] = {k: v for k, v in spec.items() if k != "required"}
        if spec.get("required", True):
            required.append(param)
    parameters: dict = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": parameters,
        },
    }


def call_tool(tool_name: str, payload: dict, config: dict | None = None) -> str:
    """调用工具；未注册抛 KeyError；执行异常转为失败说明文本（工具失败不影响主链路）。"""
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"工具未注册: {tool_name}")
    try:
        result = TOOL_REGISTRY[tool_name]["call"](payload or {}, config or {})
    except Exception as exc:  # noqa: BLE001 - 工具执行异常兜底为失败文本
        return f"[工具 {tool_name} 调用失败: {exc}]"
    text = str(result)
    limit = TOOL_REGISTRY[tool_name].get("result_max", RESULT_MAX)
    return text if limit is None or len(text) <= limit else text[:limit] + "…[截断]"


def get_config(tool_name: str) -> dict:
    """工具的 config Schema 定义（前端渲染表单用；未定义返回空）。"""
    return TOOL_REGISTRY.get(tool_name, {}).get("schema", {}).get("config", {})
