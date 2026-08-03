"""WebSearch Tool：网页搜索占位实现（M3 验证工具可扩展性）。

配置方式（二选一）：
- 智能体工具配置 tool_config.api_key（后端经 agent_tool.tool_config 透传）
- 环境变量 WEB_SEARCH_API_KEY
未配置时返回结构化"未配置"结果而非抛异常 —— 演示工具失败不阻断主链路的降级路径。
"""

import logging
import os

logger = logging.getLogger(__name__)


def web_search(query: str, config: dict | None = None) -> dict:
    """搜索网页，返回 {status, results|message}。"""
    api_key = (config or {}).get("api_key") or os.getenv("WEB_SEARCH_API_KEY", "")
    if not api_key:
        logger.info("WebSearch 未配置 API Key，返回占位结果")
        return {
            "status": "not_configured",
            "message": "搜索服务未配置 API Key，请在智能体工具配置中填写 api_key",
        }
    # 占位实现：已配置 Key 时返回结构化示例结果（后续可替换为真实搜索 API）
    return {
        "status": "ok",
        "results": [
            {
                "title": f"关于「{query}」的示例结果",
                "url": "https://example.com/search",
                "snippet": "这是搜索占位实现返回的示例结果，配置真实搜索服务后返回真实条目。",
            }
        ],
    }


SCHEMA = {
    "name": "web_search",
    "description": "搜索网页信息，返回标题、链接与摘要列表。",
    "parameters": {"query": {"type": "string", "description": "搜索关键词"}},
    "config": {
        "api_key": {"type": "string", "description": "搜索服务 API Key（可选，留空返回占位结果）"},
    },
}
