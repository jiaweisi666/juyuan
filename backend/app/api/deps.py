"""
deps.py - 依赖注入与鉴权。

- API Key 校验：Authorization: Bearer <key> 或 x-api-key，未配置则放行（本地开发）。
- 管理令牌校验：x-admin-token，未配置则放行。
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from ..config import get_settings


def _extract_api_key(authorization: str | None, x_api_key: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if authorization:
        return authorization.strip()
    return (x_api_key or "").strip()


async def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> bool:
    settings = get_settings()
    if not settings.api_key:
        return True
    provided = _extract_api_key(authorization, x_api_key)
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "无效的 API Key", "type": "authentication_error"},
        )
    return True


async def require_admin(
    x_admin_token: str | None = Header(default=None, alias="x-admin-token"),
) -> bool:
    settings = get_settings()
    if not settings.admin_token:
        return True
    if (x_admin_token or "").strip() != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "无效的管理令牌", "type": "authentication_error"},
        )
    return True
