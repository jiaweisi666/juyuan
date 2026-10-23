"""
keys_routes.py - API 密钥管理接口。

把网关聚合的各网页大模型（含 AUTO 智能路由）签发为 OpenAI / Anthropic
兼容的 API Key，供第三方应用（如 Trae、各类 SDK 客户端）直接调用。

- GET    /api/keys                  列出全部密钥（脱敏）
- POST   /api/keys                  新建密钥（仅本次返回明文）
- PUT    /api/keys/{key_id}         更新名称 / 模型授权 / 启用状态
- DELETE /api/keys/{key_id}         删除密钥
- POST   /api/keys/{key_id}/reveal  重新明文展示（本地管理面板使用）
- GET    /api/keys/meta             可授权模型清单 + 接入点信息
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..accounts.crypto import decrypt, encrypt
from ..config import get_settings
from ..platforms.loader import all_known_models, model_owner
from ..storage.db import get_database
from .deps import hash_api_key, require_admin

router = APIRouter(prefix="/api/keys", tags=["keys"], dependencies=[Depends(require_admin)])

KEY_PREFIX = "sk-juyuan-"


def _generate_key() -> str:
    return KEY_PREFIX + secrets.token_hex(24)


def _public(record: dict) -> dict:
    """返回可安全下发的密钥信息（不含明文与哈希）。"""
    return {
        "id": record["id"],
        "name": record.get("name", ""),
        "key_prefix": record.get("key_prefix", ""),
        "models": record.get("models") or [],
        "enabled": bool(record.get("enabled")),
        "created_at": record.get("created_at", 0.0),
        "last_used_at": record.get("last_used_at", 0.0),
        "usage_count": record.get("usage_count", 0),
    }


class KeyCreate(BaseModel):
    name: str = ""
    models: list[str] = []


class KeyUpdate(BaseModel):
    name: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None


@router.get("/meta")
async def key_meta() -> dict:
    """返回可授权模型清单与第三方接入所需的基础地址。"""
    settings = get_settings()
    base = f"http://{settings.host}:{settings.port}"
    # 当前仅支持 platforms.json 中声明的模型，不再暴露已下线的 AUTO 选项
    models = [{"id": m, "owned_by": model_owner(m), "label": m} for m in all_known_models()]
    return {
        "base_url": base,
        "openai_base_url": f"{base}/v1",
        "anthropic_base_url": base,
        "models": models,
    }


@router.get("")
async def list_keys() -> dict:
    return {"keys": [_public(r) for r in get_database().list_api_keys()]}


@router.post("")
async def create_key(payload: KeyCreate) -> dict:
    raw = _generate_key()
    record = get_database().create_api_key(
        key_id=uuid.uuid4().hex[:16],
        name=(payload.name or "").strip() or "未命名密钥",
        key_enc=encrypt(raw),
        key_hash=hash_api_key(raw),
        key_prefix=raw[: len(KEY_PREFIX) + 8],
        models=[m for m in payload.models if m],
    )
    return {"key": _public(record), "secret": raw}


@router.put("/{key_id}")
async def update_key(key_id: str, payload: KeyUpdate) -> dict:
    record = get_database().update_api_key(
        key_id,
        name=payload.name,
        models=[m for m in payload.models if m] if payload.models is not None else None,
        enabled=payload.enabled,
    )
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "密钥不存在"})
    return {"key": _public(record)}


@router.delete("/{key_id}")
async def delete_key(key_id: str) -> dict:
    if not get_database().delete_api_key(key_id):
        raise HTTPException(status_code=404, detail={"message": "密钥不存在"})
    return {"deleted": key_id}


@router.post("/{key_id}/reveal")
async def reveal_key(key_id: str) -> dict:
    record = get_database().get_api_key(key_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "密钥不存在"})
    return {"secret": decrypt(record.get("key_enc") or "")}
