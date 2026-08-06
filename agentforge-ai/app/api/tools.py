"""工具元数据接口 + 自定义工具测试端点。

- GET  /agent/tools/meta：全部工具 Schema（前端按 Schema 渲染配置表单）
- POST /agent/tools/test：自定义工具真实执行一次（HTTP 直发 / 代码进沙箱），
  供前端「测试」按钮与后端 ToolDefinitionController 使用
"""
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_internal_token
from app.tools import http_tool, registry as tool_registry, script_tool

router = APIRouter(prefix="/agent", tags=["tools"], dependencies=[Depends(require_internal_token)])


class ToolTestRequest(BaseModel):
    """自定义工具测试入参（定义 + 示例参数）。"""
    toolType: str = Field(description="http / script / builtin")
    toolName: str | None = Field(default=None, description="内置工具名（toolType=builtin）")
    toolConfig: dict | None = Field(default=None, description="内置工具配置（toolType=builtin）")
    httpConfig: dict | None = None
    scriptConfig: dict | None = None
    parameters: dict | None = None
    args: dict = Field(default_factory=dict, description="示例参数（LLM 视角的入参）")


class ToolTestResponse(BaseModel):
    """执行结果：ok=false 时 error 为可读失败原因（Timeout/HTTP 状态/语法错误等）。"""
    ok: bool
    result: Any = None
    stdout: str = ""
    error: str = ""
    durationMs: int = 0


@router.get("/tools/meta")
def tools_meta() -> list[dict]:
    """全部已注册工具的名称/描述/参数/配置 Schema。"""
    return tool_registry.list_tool_meta()


@router.post("/tools/test")
def tools_test(request: ToolTestRequest) -> ToolTestResponse:
    """测试自定义工具：HTTP 工具直发请求（SSRF 防护生效）；代码工具进沙箱受限执行。

    任何失败均返回 ok=false + 可读错误（不抛异常，避免后端误判为系统错误）。
    """
    start = time.monotonic()
    try:
        if request.toolType == "http":
            result: Any = http_tool.execute(request.httpConfig or {}, request.args or {})
            stdout = ""
        elif request.toolType == "script":
            result = script_tool.execute(request.scriptConfig or {}, request.args or {})
            stdout = ""
        elif request.toolType == "builtin":
            result = tool_registry.call_tool(
                request.toolName or "", request.args or {}, request.toolConfig or {})
            stdout = ""
        else:
            raise ValueError(f"toolType 仅支持 http / script / builtin: {request.toolType}")
    except Exception as exc:  # noqa: BLE001 - 测试失败转可读错误，非系统异常
        return ToolTestResponse(ok=False, error=str(exc),
                                durationMs=int((time.monotonic() - start) * 1000))
    return ToolTestResponse(ok=True, result=result, stdout=stdout,
                            durationMs=int((time.monotonic() - start) * 1000))
