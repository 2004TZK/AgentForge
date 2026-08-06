"""工具注册表：name → {call, schema}。新增工具只需注册即可被 LLM/Workflow 使用。

- schema 结构：{"name", "description", "parameters": {参数名: {type, description, required?}},
  "config": {配置参数名: {type, description}}} —— config 为智能体级配置（存 agent_tool.tool_config，
  前端按 Schema 渲染配置表单），不进 LLM 工具参数
- call(payload, config)：payload 为 LLM 工具调用参数；config 为智能体工具配置
- M3 起支持 OpenAI 兼容 tools 参数格式（type=function），供 Ollama 原生 API / OpenAI 兼容接口使用
- M5 起支持自定义工具请求级定义：schema 直接生成、执行闭包随请求构建，
  不写入全局注册表（避免多请求同名工具并发串扰）
"""
import logging

from app.tools import (
    calculator,
    current_time,
    github,
    http_tool,
    script_tool,
    star_chart,
    star_electional,
    star_progression,
    star_synastry,
    star_transit,
    web_search,
)


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


def _transit_chart(payload: dict, config: dict | None = None) -> str:
    return star_transit.run(payload, config)


def _progression_chart(payload: dict, config: dict | None = None) -> str:
    return star_progression.run(payload, config)


def _synastry_chart(payload: dict, config: dict | None = None) -> str:
    return star_synastry.run(payload, config)


def _electional_chart(payload: dict, config: dict | None = None) -> str:
    return star_electional.run(payload, config)


TOOL_REGISTRY = {
    "calculator": {"call": _calc, "schema": calculator.SCHEMA},
    "github": {"call": _github, "schema": github.SCHEMA},
    "current_time": {"call": _current_time, "schema": current_time.SCHEMA},
    "web_search": {"call": _web_search, "schema": web_search.SCHEMA},
    # 星盘类工具出参为完整 JSON（数 KB），禁用结果截断，保证 LLM 拿到全量数据
    "star_chart": {"call": _star_chart, "schema": star_chart.SCHEMA, "result_max": None},
    "transit_chart": {"call": _transit_chart, "schema": star_transit.SCHEMA, "result_max": None},
    "progression_chart": {"call": _progression_chart, "schema": star_progression.SCHEMA, "result_max": None},
    "synastry_chart": {"call": _synastry_chart, "schema": star_synastry.SCHEMA, "result_max": None},
    "electional_chart": {"call": _electional_chart, "schema": star_electional.SCHEMA, "result_max": None},
}

logger = logging.getLogger(__name__)

# 工具执行结果的展示截断长度（防超长结果污染对话/日志）
RESULT_MAX = 500


def is_registered(tool_name: str) -> bool:
    return tool_name in TOOL_REGISTRY


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())


# ---------------- 自定义工具（M5，请求级定义，不污染全局注册表） ----------------

def build_custom_handler(definition: dict):
    """根据工具定义构造执行闭包（HTTP 直发 / 代码进沙箱）。

    definition: {name, description, parameters, httpConfig?/scriptConfig?}
    返回 call(payload, config) -> str；定义缺少可执行配置时抛 ValueError。
    """
    http_config = definition.get("httpConfig")
    script_config = definition.get("scriptConfig")
    if http_config:
        return lambda payload, config=None: http_tool.execute(http_config, payload)
    if script_config:
        return lambda payload, config=None: script_tool.execute(script_config, payload)
    raise ValueError(f"工具定义 {definition.get('name')} 缺少 httpConfig/scriptConfig")


def build_custom_schema(definition: dict) -> dict:
    """自定义工具定义 → 注册表 schema 结构（parameters 已是 OpenAI 格式，直接透传）。"""
    return {
        "name": definition.get("name"),
        "description": definition.get("description", ""),
        "parameters": definition.get("parameters") or {"type": "object", "properties": {}},
    }


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


def openai_tools(tool_names: list[str], custom_tools: list[dict] | None = None) -> list[dict]:
    """将工具名列表转换为 OpenAI/Ollama 兼容的 tools 参数格式。

    custom_tools: 自定义工具定义列表（{name, description, parameters}，
    parameters 为 OpenAI function parameters 结构），仅当名称在 tool_names 中时输出。
    自定义工具直接由请求级定义生成 schema（不写入全局 TOOL_REGISTRY，
    避免多请求同名工具并发串扰）；执行由请求级 handler 负责。
    """
    custom_by_name = {d.get("name"): d for d in (custom_tools or []) if d.get("name")}
    result: list[dict] = []
    for name in tool_names:
        if name in custom_by_name:
            result.append(_to_openai_function(build_custom_schema(custom_by_name[name])))
        elif name in TOOL_REGISTRY:
            result.append(to_openai_tool(name))
    return result


def to_openai_tool(tool_name: str) -> dict:
    """内置工具 → OpenAI function 格式（type=function）。"""
    return _to_openai_function(TOOL_REGISTRY[tool_name]["schema"])


def _to_openai_function(schema: dict) -> dict:
    """注册表 schema → OpenAI function 格式。

    内置工具 parameters 为扁平参数描述，转换为 {"type": "object", "properties": {...}}；
    自定义工具（M5）parameters 已是 OpenAI function parameters 结构，直接透传。
    """
    parameters: dict = schema.get("parameters", {})
    if isinstance(parameters, dict) and "type" in parameters and "properties" in parameters:
        openai_parameters: dict = parameters
    else:
        properties: dict = {}
        required: list[str] = []
        for param, spec in parameters.items():
            properties[param] = {k: v for k, v in spec.items() if k != "required"}
            if spec.get("required", True):
                required.append(param)
        openai_parameters = {"type": "object", "properties": properties}
        if required:
            openai_parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": openai_parameters,
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
