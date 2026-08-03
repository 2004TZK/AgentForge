"""Planner：意图识别与工具决策。

Phase 2 为简化规则实现（关键字启发式）；Phase 4 演进为 LLM 自主规划
（planner → RAG/工具分支 → LLM → 输出的完整循环）。
"""
import logging
import re

logger = logging.getLogger(__name__)

_MATH_PATTERN = re.compile(r"[\d\s+\-*/%^().]+\d[\s+\-*/%^().]*$")


def decide_tools(message: str, enabled_tools: list[str]) -> list[str]:
    """根据消息内容与 Agent 启用的工具，返回应调用的工具列表。"""
    if not enabled_tools:
        return []
    chosen = []
    if "calculator" in enabled_tools and _MATH_PATTERN.match(message.strip()):
        chosen.append("calculator")
    if "github" in enabled_tools and re.search(r"github\s*[:：]?\s*[\w-]+/[\w.-]+", message, re.I):
        chosen.append("github")
    logger.debug("Planner 决策: tools=%s", chosen)
    return chosen
