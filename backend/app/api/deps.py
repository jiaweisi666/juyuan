"""
deps.py - 依赖注入与鉴权。

- API Key 校验：Authorization: Bearer <key> 或 x-api-key。
  * 静态主 Key（GATEWAY_API_KEY）：拥有全部模型权限；
  * 动态 Key（面板生成，存于 SQLite）：按绑定的模型白名单授权；
  * 未配置任何 Key 时放行（仅建议本机 127.0.0.1 使用）。
- 管理令牌校验：x-admin-token，未配置则放行。
"""

from __future__ import annotations

import hashlib

from fastapi import Header, HTTPException, Request, status

from ..config import get_settings
from ..storage.db import get_database


def hash_api_key(raw: str) -> str:
    """API Key 的存储/校验摘要（SHA-256 十六进制）。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuthContext:
    """一次请求的鉴权上下文。"""

    def __init__(
        self,
        *,
        master: bool = False,
        key_id: str = "",
        key_name: str = "",
        allowed_models: list[str] | None = None,
    ) -> None:
        self.master = master
        self.key_id = key_id
        self.key_name = key_name
        self.allowed_models = allowed_models

    @property
    def restricted(self) -> bool:
        """是否受模型白名单约束（None 表示不限制）。"""
        return self.allowed_models is not None

    def allows(self, model: str) -> bool:
        if self.allowed_models is None:
            return True
        return (model or "").strip() in self.allowed_models


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
) -> AuthContext:
    settings = get_settings()
    provided = _extract_api_key(authorization, x_api_key)

    # 1) 静态主 Key：全量权限
    if settings.api_key and provided == settings.api_key:
        ctx = AuthContext(master=True)
        request.state.auth = ctx
        return ctx

    # 2) 动态 Key：按模型白名单授权
    db = get_database()
    if provided:
        record = db.find_api_key_by_hash(hash_api_key(provided))
        if record and record["enabled"]:
            db.touch_api_key(record["id"])
            models = record.get("models") or []
            ctx = AuthContext(
                key_id=record["id"],
                key_name=record.get("name", ""),
                allowed_models=list(models) if models else None,
            )
            request.state.auth = ctx
            return ctx

    # 3) 未配置任何密钥 → 本机免鉴权
    if not settings.api_key and db.count_api_keys() == 0:
        ctx = AuthContext(master=True)
        request.state.auth = ctx
        return ctx

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": "无效的 API Key", "type": "authentication_error"},
    )


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
