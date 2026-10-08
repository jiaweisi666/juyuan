"""
admin_routes.py - 管理面板接口。

覆盖：平台状态、账号管理、路由配置、模型画像、日志与统计、反馈。
所有接口默认要求 x-admin-token（未配置则放行，仅监听 127.0.0.1）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..accounts.crypto import decrypt, mask
from ..accounts.pool import get_pool
from ..config import get_settings
from ..platforms.catalog import refresh as refresh_model_catalog
from ..platforms.catalog import snapshot as model_catalog_snapshot
from ..platforms.loader import all_known_models, model_owner
from ..platforms.registry import get_registry
from ..router.engine import get_router
from ..storage.db import get_database
from .deps import require_admin

router = APIRouter(prefix="/api", tags=["admin"], dependencies=[Depends(require_admin)])


# --------------------------------------------------------------------------- #
# 模型目录（随底座 /v1/models 动态迭代）
# --------------------------------------------------------------------------- #
@router.get("/models")
async def list_models() -> dict:
    """前端模型清单（含 AUTO），随底座模型自动迭代。"""
    data = [{"id": "auto", "owned_by": "juyuan"}]
    data += [{"id": m, "owned_by": model_owner(m)} for m in all_known_models()]
    return {"data": data, "catalog": model_catalog_snapshot()}


@router.get("/models/catalog")
async def get_model_catalog() -> dict:
    return model_catalog_snapshot()


@router.post("/models/refresh")
async def sync_model_catalog() -> dict:
    """手动从底座同步模型清单（网页端迭代后可用）。"""
    return await refresh_model_catalog(force=True)


# --------------------------------------------------------------------------- #
# 平台
# --------------------------------------------------------------------------- #
@router.get("/platforms")
async def list_platforms() -> dict:
    registry = get_registry()
    pool = get_pool()
    items = registry.describe()
    accounts = pool.store.all()
    for item in items:
        pid = item["platform_id"]
        item["account_count"] = sum(1 for a in accounts if a.platform == pid)
    return {"platforms": items}


@router.post("/platforms/{platform_id}/test")
async def test_platform(platform_id: str) -> dict:
    registry = get_registry()
    plugin = registry.get(platform_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail={"message": f"平台不存在: {platform_id}"})
    ok = await plugin.health_check()
    return {"platform": platform_id, "healthy": ok, "adapter": plugin.describe().get("adapter")}


# --------------------------------------------------------------------------- #
# 账号
# --------------------------------------------------------------------------- #
class AccountCreate(BaseModel):
    platform: str
    email: str = ""
    session_key: str = ""
    cookies: dict[str, Any] | str = ""
    remark: str = ""


class AccountUpdate(BaseModel):
    email: str | None = None
    remark: str | None = None
    status: str | None = None
    session_key: str | None = None
    cookies: dict[str, Any] | str | None = None


class AccountImport(BaseModel):
    accounts: list[dict[str, Any]]


def _public_account(account) -> dict:
    return account.to_public(
        masked_session=mask(decrypt(account.session_key_enc)),
        masked_cookies=mask(decrypt(account.cookies_enc)),
    )


@router.get("/accounts")
async def list_accounts() -> dict:
    pool = get_pool()
    pool.store.maybe_reload()
    return {"accounts": [_public_account(a) for a in pool.store.all()], "summary": pool.status()}


@router.post("/accounts")
async def create_account(payload: AccountCreate) -> dict:
    pool = get_pool()
    account, msg = pool.store.add(
        platform=payload.platform,
        email=payload.email,
        session_key=payload.session_key,
        cookies=payload.cookies,
        remark=payload.remark,
    )
    if account is None:
        raise HTTPException(status_code=409, detail={"message": msg})
    return {"account": _public_account(account)}


@router.put("/accounts/{account_id}")
async def update_account(account_id: str, payload: AccountUpdate) -> dict:
    pool = get_pool()
    account = pool.store.update(account_id, **payload.model_dump(exclude_none=True))
    if account is None:
        raise HTTPException(status_code=404, detail={"message": "账号不存在"})
    return {"account": _public_account(account)}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str) -> dict:
    pool = get_pool()
    if not pool.store.delete(account_id):
        raise HTTPException(status_code=404, detail={"message": "账号不存在"})
    return {"deleted": account_id}


@router.post("/accounts/import")
async def import_accounts(payload: AccountImport) -> dict:
    pool = get_pool()
    return pool.store.import_batch(payload.accounts)


@router.post("/accounts/health-check")
async def accounts_health_check() -> dict:
    registry = get_registry()
    pool = get_pool()

    async def check(platform_id: str) -> dict:
        plugin = registry.get(platform_id)
        if plugin is None:
            return {"platform": platform_id, "healthy": False}
        return {"platform": platform_id, "healthy": await plugin.health_check()}

    platforms = pool.store.platforms() or registry.ids()
    results = [await check(pid) for pid in platforms]
    return {"results": results}


# --------------------------------------------------------------------------- #
# 路由配置
# --------------------------------------------------------------------------- #
class WeightUpdate(BaseModel):
    accuracy: float
    latency: float
    cost: float


@router.get("/routing/weights")
async def get_weights() -> dict:
    return {"weights": get_router().weights}


@router.put("/routing/weights")
async def set_weights(payload: WeightUpdate) -> dict:
    return {"weights": get_router().update_weights(payload.accuracy, payload.latency, payload.cost)}


class RoutingConfig(BaseModel):
    auto_router_enabled: bool | None = None
    feedback_optimize: bool | None = None


def _routing_config() -> dict:
    settings = get_settings()
    return {
        "auto_router_enabled": settings.auto_router_enabled,
        "feedback_optimize": settings.feedback_optimize,
        "real_browser_enabled": settings.real_browser_enabled,
    }


@router.get("/routing/config")
async def get_routing_config() -> dict:
    return _routing_config()


@router.put("/routing/config")
async def set_routing_config(payload: RoutingConfig) -> dict:
    settings = get_settings()
    if payload.auto_router_enabled is not None:
        settings.auto_router_enabled = payload.auto_router_enabled
    if payload.feedback_optimize is not None:
        settings.feedback_optimize = payload.feedback_optimize
    return _routing_config()



@router.get("/routing/profiles")
async def get_profiles() -> dict:
    return {"profiles": get_router()._profiles.snapshot()}  # noqa: SLF001


@router.get("/routing/decisions")
async def get_decisions(limit: int = 50) -> dict:
    return {"decisions": get_database().list_routes(limit=limit)}


class FeedbackPayload(BaseModel):
    call_log_id: str = ""
    platform: str
    variant: str = "default"
    rating: str  # up / down
    comment: str = ""
    task_type: str = "general"


@router.post("/feedback")
async def submit_feedback(payload: FeedbackPayload) -> dict:
    db = get_database()
    fb_id = db.add_feedback(payload.call_log_id, payload.rating, payload.comment)
    get_router().apply_feedback(payload.platform, payload.variant, payload.rating, payload.task_type)
    return {"feedback_id": fb_id, "applied": True}


# --------------------------------------------------------------------------- #
# 日志与统计
# --------------------------------------------------------------------------- #
@router.get("/logs")
async def list_logs(limit: int = 100, offset: int = 0, status: str = "", platform: str = "") -> dict:
    return {"logs": get_database().list_calls(limit=limit, offset=offset, status=status, platform=platform)}


@router.get("/stats/summary")
async def stats_summary() -> dict:
    return get_database().stats_summary()


@router.get("/stats/series")
async def stats_series(hours: int = 24) -> dict:
    return {"series": get_database().stats_series(hours=hours)}
