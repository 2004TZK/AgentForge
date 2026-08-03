"""公共依赖：内部鉴权（X-Internal-Token，与后端 JWT 体系隔离）。"""
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    """校验内部请求头；不匹配返回 401。"""
    if not x_internal_token or not secrets.compare_digest(x_internal_token, settings.internal_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="内部鉴权失败")
