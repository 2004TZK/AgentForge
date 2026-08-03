"""工具注册表：name → {call, schema}。新增工具只需注册即可被 Planner/Agent Runtime 使用。"""
from app.tools import calculator, github


def _calc(payload: dict) -> str:
    return str(calculator.evaluate(payload.get("expression", "")))


def _github(payload: dict) -> str:
    import json
    return json.dumps(github.query_repo(payload.get("repo", "")), ensure_ascii=False)


TOOL_REGISTRY = {
    "calculator": {"call": _calc, "schema": calculator.SCHEMA},
    "github": {"call": _github, "schema": github.SCHEMA},
}


def is_registered(tool_name: str) -> bool:
    return tool_name in TOOL_REGISTRY


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())


def call_tool(tool_name: str, payload: dict) -> str:
    """调用工具；未注册抛 KeyError。"""
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"工具未注册: {tool_name}")
    return TOOL_REGISTRY[tool_name]["call"](payload)
