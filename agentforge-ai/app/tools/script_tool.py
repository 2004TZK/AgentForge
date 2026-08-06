"""代码自定义工具执行器（工具定义开发文档 v3.0 §7 阶段三）。

将 {代码, 参数} POST 给 sandbox 服务受限执行（无外网 / 非 root / 资源限制 / 只读文件系统），
返回结果/错误/耗时；执行失败转为可读失败文本（不阻断对话主链路）。
"""
import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_LANGUAGES = {"python", "javascript"}


def execute(config: dict, params: dict) -> str:
    """执行代码工具：校验定义 → 调 sandbox /run → 返回可读结果。

    - 代码大小 ≤ 50KB（前端/后端已双重校验，此处兜底）
    - 结果统一序列化为字符串回填 LLM（与内置工具一致）
    """
    config = config or {}
    language = str(config.get("language", ""))
    source = config.get("source")
    if language not in _ALLOWED_LANGUAGES:
        raise ValueError(f"script_config.language 仅支持 python / javascript: {language}")
    if not source or not str(source).strip():
        raise ValueError("代码为空，无法执行")
    if len(str(source)) > settings.script_tool_max_source_chars:
        raise ValueError(f"代码大小超过 {settings.script_tool_max_source_chars // 1024}KB 上限")

    payload = {
        "language": language,
        "source": str(source),
        "args": params or {},
        "limits": {
            "timeoutSeconds": settings.http_tool_timeout_seconds,
            "memoryMb": 256,
        },
    }
    try:
        # trust_env=False：sandbox 为内部服务，不应受 HTTP_PROXY/HTTPS_PROXY 环境变量影响
        with httpx.Client(timeout=60, trust_env=False) as client:
            response = client.post(
                f"{settings.sandbox_base_url}/run",
                json=payload,
                headers={"X-Internal-Token": settings.sandbox_internal_token},
            )
    except httpx.RequestError as exc:
        raise ConnectionError(f"沙箱执行器不可用: {exc}") from exc

    if response.status_code != 200:
        raise ConnectionError(f"沙箱执行器返回 HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise ConnectionError("沙箱执行器返回非法响应") from exc

    if data.get("ok"):
        result = data.get("result")
        stdout = str(data.get("stdout") or "")
        text = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) \
            else str(result)
        if stdout:
            text = f"{text}\n[stdout]\n{stdout[: settings.script_tool_max_stdout_chars]}"
        return text
    # 执行失败/被限制：返回可读错误（Timeout / Memory / Syntax / Runtime）
    error = str(data.get("error") or "UnknownError")
    raise RuntimeError(f"代码执行失败: {error}")
