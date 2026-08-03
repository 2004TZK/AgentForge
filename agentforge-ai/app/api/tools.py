"""工具元数据接口：GET /agent/tools/meta（前端按 Schema 渲染配置表单，后端透传）。"""
from fastapi import APIRouter, Depends

from app.api.deps import require_internal_token
from app.tools import registry as tool_registry

router = APIRouter(prefix="/agent", tags=["tools"], dependencies=[Depends(require_internal_token)])


@router.get("/tools/meta")
def tools_meta() -> list[dict]:
    """全部已注册工具的名称/描述/参数/配置 Schema。"""
    return tool_registry.list_tool_meta()
