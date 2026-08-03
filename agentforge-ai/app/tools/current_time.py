"""CurrentTime Tool：返回当前日期时间（离线可用，验证 LLM 工具选择的确定性场景）。"""


def current_time(time_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """返回当前时间，time_format 为 strftime 格式（默认 %Y-%m-%d %H:%M:%S）。

    非法格式校验：Linux 下 strftime 抛 ValueError；Windows 下未知指令原样透传，
    输出中残留 '%' 即视为非法（两种平台行为统一）。
    """
    from datetime import datetime

    try:
        result = datetime.now().strftime(time_format)
    except ValueError as exc:
        raise ValueError(f"时间格式非法: {time_format}") from exc
    if "%" in result:
        raise ValueError(f"时间格式非法: {time_format}")
    return result


SCHEMA = {
    "name": "current_time",
    "description": "获取当前日期与时间，如 2026-08-03 15:30:00。",
    "parameters": {
        "time_format": {
            "type": "string",
            "description": "可选的时间格式（strftime 语法），默认 %Y-%m-%d %H:%M:%S",
            "required": False,
        },
    },
    "config": {},
}
