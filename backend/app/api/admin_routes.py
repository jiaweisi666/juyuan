"""
admin_routes.py - 管理面板接口。

覆盖：平台状态、账号管理、路由配置、模型画像、日志与统计、反馈。
所有接口默认要求 x-admin-token（未配置则放行，仅监听 127.0.0.1）。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..accounts.crypto import decrypt, mask
from ..accounts.pool import get_pool
from ..browser.cdp import CDPError, apply_login, find_page, read_local_storage
from ..config import get_settings
from ..logging_config import get_logger
from ..platforms.catalog import refresh as refresh_model_catalog
from ..platforms.catalog import snapshot as model_catalog_snapshot
from ..platforms.loader import (
    all_known_models,
    get_platform_definition,
    load_platform_definitions,
    model_owner,
)
from ..platforms.registry import get_registry
from ..router.engine import get_router
from ..storage.db import get_database
from .deps import require_admin

router = APIRouter(prefix="/api", tags=["admin"], dependencies=[Depends(require_admin)])

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# 模型目录（随底座 /v1/models 动态迭代）
# --------------------------------------------------------------------------- #
@router.get("/models")
async def list_models() -> dict:
    """前端模型清单：仅暴露当前正式支持的模型（不再包含 AUTO）。"""
    data = [{"id": m, "owned_by": model_owner(m)} for m in all_known_models()]
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
    accounts = pool.store.all()
    plugins = list(registry.all())

    # 并发探测真实状态（避免底座不可达时逐平台串行等待导致接口超时），消除「就绪假象」
    await asyncio.gather(
        *(plugin.health_check() for plugin in plugins), return_exceptions=True
    )

    items = []
    for plugin in plugins:
        item = plugin.describe()
        item["account_count"] = sum(1 for a in accounts if a.platform == plugin.platform_id)
        items.append(item)
    return {"platforms": items}


@router.post("/platforms/{platform_id}/test")
async def test_platform(platform_id: str) -> dict:
    registry = get_registry()
    plugin = registry.get(platform_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail={"message": f"平台不存在: {platform_id}"})
    ok = await plugin.health_check()
    desc = plugin.describe()
    return {
        "platform": platform_id,
        "healthy": ok,
        "adapter": desc.get("adapter"),
        "reason": desc.get("health_reason") or "",
    }


# --------------------------------------------------------------------------- #
# 账号
# --------------------------------------------------------------------------- #
class AccountCreate(BaseModel):
    platform: str
    email: str = ""
    session_key: str = ""
    cookies: dict[str, Any] | str = ""
    storage: dict[str, Any] | str = ""
    remark: str = ""


class AccountUpdate(BaseModel):
    email: str | None = None
    remark: str | None = None
    status: str | None = None
    session_key: str | None = None
    cookies: dict[str, Any] | str | None = None
    storage: dict[str, Any] | str | None = None


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
        storage=payload.storage,
        remark=payload.remark,
    )
    if account is None:
        raise HTTPException(status_code=409, detail={"message": msg})
    response: dict[str, Any] = {"account": _public_account(account)}
    # 手动填入登录态后，尽力注入受控浏览器，使平台立即可用
    if account.cookies_enc or account.storage_enc:
        definition = get_platform_definition(account.platform)
        if definition is not None:
            try:
                response["applied"] = await _apply_login_to_browser(
                    definition, decrypt(account.cookies_enc), decrypt(account.storage_enc)
                )
            except HTTPException as exc:
                detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
                response["apply_error"] = detail
    return response


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
            return {"platform": platform_id, "healthy": False, "reason": "平台未注册"}
        try:
            healthy = await plugin.health_check()
        except Exception as exc:  # noqa: BLE001
            return {"platform": platform_id, "healthy": False, "reason": f"体检异常：{exc}"}
        reason = "" if healthy else (plugin.describe().get("health_reason") or "")
        return {"platform": platform_id, "healthy": healthy, "reason": reason}

    platforms = pool.store.platforms() or registry.ids()
    results = await asyncio.gather(*(check(pid) for pid in platforms))
    return {"results": list(results)}


# --------------------------------------------------------------------------- #
# 账号导入：从受控浏览器一键读取登录态（点击即实时读取）
# --------------------------------------------------------------------------- #
class OpenLoginRequest(BaseModel):
    platform: str


def _auto_identity(definition: dict[str, Any]) -> str:
    """自动导入账号的去重标识（同一平台重复点击仅更新 Cookie）。"""
    site = str(definition.get("site_key") or definition.get("id") or "").strip()
    return f"auto@{site}"


def _upsert_auto_account(
    store, definition: dict[str, Any], cookies: Any, storage: Any = None
) -> tuple[str, Any]:
    """把某平台登录态（Cookie + localStorage）写入账号池（已存在则更新）。返回 (状态, 账号)。"""
    pid = str(definition.get("id") or "").strip()
    identity = _auto_identity(definition)
    current = next(
        (a for a in store.all() if a.platform == pid and a.email.lower() == identity.lower()),
        None,
    )
    extra: dict[str, Any] = {"storage": storage} if storage else {}
    if current is not None:
        store.update(current.id, cookies=cookies, **extra)
        return "updated", current
    account, _msg = store.add(
        platform=pid,
        email=identity,
        cookies=cookies,
        storage=storage or "",
        remark="自动导入（浏览器登录态）",
    )
    return ("added" if account is not None else "skipped"), account


async def _base_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """调用底座（universal-web-api）本机 HTTP 接口。"""
    base = (get_settings().base_web_api_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail={"message": "未配置底座地址（base_web_api_url）"})
    headers: dict[str, str] = {}
    api_key = (get_settings().base_web_api_key or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        # 底座监听本机回环地址，禁用环境/系统代理，避免被本机代理（如 Clash）拦截转发出 502
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            resp = await client.post(f"{base}{path}", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={"message": f"底座不可达：{exc}"}) from exc
    if resp.status_code == 503:
        raise HTTPException(
            status_code=503,
            detail={"message": "受控浏览器未连接：请确认受控浏览器已在 9222 端口运行后重试"},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail={"message": f"底座返回 {resp.status_code}"})
    try:
        return resp.json()
    except ValueError:
        return {}


@router.post("/accounts/auto-import")
async def auto_import_accounts() -> dict:
    """扫描受控浏览器已登录的站点，读取 Cookie 写入账号池；重复点击即刷新 Cookie。"""
    pool = get_pool()
    store = pool.store
    store.maybe_reload()

    added = updated = skipped = 0
    results: list[dict[str, Any]] = []
    for definition in load_platform_definitions():
        pid = str(definition.get("id") or "").strip()
        homepage = str(definition.get("homepage") or "").strip()
        if not pid or not homepage:
            continue
        try:
            data = await _base_post("/api/browser/read-cookies", {"url": homepage})
        except HTTPException as exc:
            detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
            results.append({"platform": pid, "status": "error", "detail": detail})
            continue
        cookies = data.get("cookies") or []
        count = int(data.get("count") or len(cookies))
        if count <= 0:
            results.append({"platform": pid, "status": "empty", "cookie_count": 0})
            continue

        status, account = _upsert_auto_account(store, definition, cookies, await _read_browser_storage(definition))
        if status == "updated":
            updated += 1
        elif status == "added":
            added += 1
        else:
            skipped += 1
        results.append({"platform": pid, "status": status, "cookie_count": count})

    return {"added": added, "updated": updated, "skipped": skipped, "results": results}


@router.post("/accounts/read-import")
async def read_import_account(payload: OpenLoginRequest) -> dict:
    """读取指定平台登录态 Cookie 并写入账号池（登录导入轮询用）。

    与 auto-import 的区别：只处理单一平台，且不依赖全量扫描；
    供前端在「打开登录页 → 用户完成登录」后轮询，检测到登录态即自动落库。
    """
    definition = get_platform_definition(payload.platform)
    if definition is None:
        raise HTTPException(status_code=404, detail={"message": f"平台不存在: {payload.platform}"})
    homepage = str(definition.get("homepage") or "").strip()
    if not homepage:
        raise HTTPException(status_code=400, detail={"message": "该平台未配置登录页地址"})

    data = await _base_post("/api/browser/read-cookies", {"url": homepage})
    cookies = data.get("cookies") or []
    if not cookies:
        return {"status": "empty", "platform": payload.platform, "cookie_count": 0}

    pool = get_pool()
    store = pool.store
    store.maybe_reload()
    storage = await _read_browser_storage(definition)
    status, account = _upsert_auto_account(store, definition, cookies, storage)
    return {
        "status": status,
        "platform": payload.platform,
        "cookie_count": len(cookies),
        "storage_count": len(storage),
        "account": _public_account(account) if account is not None else None,
    }


@router.post("/accounts/open-login")
async def open_login_page(payload: OpenLoginRequest) -> dict:
    """在受控浏览器中打开平台官方登录页，供用户登录后一键导入。"""
    definition = get_platform_definition(payload.platform)
    if definition is None:
        raise HTTPException(status_code=404, detail={"message": f"平台不存在: {payload.platform}"})
    homepage = str(definition.get("homepage") or "").strip()
    if not homepage:
        raise HTTPException(status_code=400, detail={"message": "该平台未配置登录页地址"})
    data = await _base_post("/api/browser/open-url", {"url": homepage})
    return {"success": bool(data.get("success")), "url": homepage}


# --------------------------------------------------------------------------- #
# 登录态注入：把账号池 Cookie 写入受控浏览器（导入即登录）
# --------------------------------------------------------------------------- #
def _definition_host(definition: dict[str, Any]) -> str:
    """平台站点域名（取自 site_key / homepage）。"""
    raw = str(definition.get("site_key") or definition.get("homepage") or "").strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    return raw.split("/", 1)[0].strip().lower()


async def _read_browser_storage(definition: dict[str, Any]) -> dict[str, str]:
    """读取受控浏览器中该平台标签页的 localStorage（用于登录导入落库）。"""
    host = _definition_host(definition)
    if not host:
        return {}
    try:
        return await asyncio.to_thread(read_local_storage, host)
    except CDPError as exc:
        logger.warning("读取 %s localStorage 失败：%s", host, exc)
        return {}


async def _apply_login_to_browser(
    definition: dict[str, Any], cookies: Any, storage: Any = None
) -> dict[str, Any]:
    """把某平台的登录态（Cookie + localStorage）注入受控浏览器对应标签页并刷新（CDP）。"""
    host = _definition_host(definition)
    if not host:
        raise HTTPException(status_code=400, detail={"message": "该平台未配置站点域名"})
    try:
        return await asyncio.to_thread(apply_login, host, cookies=cookies, storage=storage)
    except CDPError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc


async def _ensure_browser_page(definition: dict[str, Any]) -> None:
    """确保受控浏览器中已有该平台标签页；仅在确实没有时才新开一个。

    之前「应用登录态」无条件调用 open-url，配合前端失败回退，会一次点出 3 个标签页。
    这里改为「有则复用、无则只开一个，并等待页面可写 localStorage」。
    """
    host = _definition_host(definition)
    if not host:
        return
    if await asyncio.to_thread(find_page, host) is not None:
        return
    homepage = str(definition.get("homepage") or "").strip()
    if not homepage:
        return
    try:
        await _base_post("/api/browser/open-url", {"url": homepage})
    except HTTPException as exc:
        detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
        raise HTTPException(status_code=502, detail={"message": f"打开 {host} 页面失败：{detail}"}) from exc
    # 等待新标签页出现（最多约 8 秒），避免刚 open-url 就注入导致 localStorage 访问被拒
    for _ in range(32):
        if await asyncio.to_thread(find_page, host) is not None:
            return
        await asyncio.sleep(0.25)
    raise HTTPException(
        status_code=502,
        detail={"message": f"已尝试打开 {host}，但受控浏览器中未出现对应标签页，请稍后重试"},
    )


@router.post("/accounts/{account_id}/apply")
async def apply_account_login(account_id: str) -> dict:
    """把指定账号的登录态（Cookie + localStorage）注入受控浏览器，使其直接进入登录态。"""
    pool = get_pool()
    account = pool.store.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail={"message": "账号不存在"})
    definition = get_platform_definition(account.platform)
    if definition is None:
        raise HTTPException(status_code=404, detail={"message": f"平台不存在: {account.platform}"})
    cookies = decrypt(account.cookies_enc)
    storage = decrypt(account.storage_enc)
    if not cookies and not storage:
        raise HTTPException(status_code=400, detail={"message": "该账号未配置登录态，无法应用到浏览器"})
    # 仅在缺少标签页时打开一次；已有标签页直接复用
    await _ensure_browser_page(definition)
    result = await _apply_login_to_browser(definition, cookies, storage)
    return {"success": True, "platform": account.platform, **result}


# --------------------------------------------------------------------------- #
# 路由配置（已屏蔽）
# --------------------------------------------------------------------------- #
# class WeightUpdate(BaseModel):
#     accuracy: float
#     latency: float
#     cost: float
#
#
# @router.get("/routing/weights")
# async def get_weights() -> dict:
#     return {"weights": get_router().weights}
#
#
# @router.put("/routing/weights")
# async def set_weights(payload: WeightUpdate) -> dict:
#     return {"weights": get_router().update_weights(payload.accuracy, payload.latency, payload.cost)}
#
#
# class RoutingConfig(BaseModel):
#     auto_router_enabled: bool | None = None
#     feedback_optimize: bool | None = None
#
#
# def _routing_config() -> dict:
#     settings = get_settings()
#     return {
#         "auto_router_enabled": settings.auto_router_enabled,
#         "feedback_optimize": settings.feedback_optimize,
#         "real_browser_enabled": settings.real_browser_enabled,
#     }
#
#
# @router.get("/routing/config")
# async def get_routing_config() -> dict:
#     return _routing_config()
#
#
# @router.put("/routing/config")
# async def set_routing_config(payload: RoutingConfig) -> dict:
#     settings = get_settings()
#     if payload.auto_router_enabled is not None:
#         settings.auto_router_enabled = payload.auto_router_enabled
#     if payload.feedback_optimize is not None:
#         settings.feedback_optimize = payload.feedback_optimize
#     return _routing_config()
#
#
# @router.get("/routing/profiles")
# async def get_profiles() -> dict:
#     return {"profiles": get_router()._profiles.snapshot()}  # noqa: SLF001
#
#
# @router.get("/routing/decisions")
# async def get_decisions(limit: int = 50) -> dict:
#     return {"decisions": get_database().list_routes(limit=limit)}
#
#
# class FeedbackPayload(BaseModel):
#     call_log_id: str = ""
#     platform: str
#     variant: str = "default"
#     rating: str  # up / down
#     comment: str = ""
#     task_type: str = "general"
#
#
# @router.post("/feedback")
# async def submit_feedback(payload: FeedbackPayload) -> dict:
#     db = get_database()
#     fb_id = db.add_feedback(payload.call_log_id, payload.rating, payload.comment)
#     get_router().apply_feedback(payload.platform, payload.variant, payload.rating, payload.task_type)
#     return {"feedback_id": fb_id, "applied": True}


# --------------------------------------------------------------------------- #
# 日志与统计（已屏蔽）
# --------------------------------------------------------------------------- #
# @router.get("/logs")
# async def list_logs(limit: int = 100, offset: int = 0, status: str = "", platform: str = "") -> dict:
#     return {"logs": get_database().list_calls(limit=limit, offset=offset, status=status, platform=platform)}
#
#
# @router.get("/stats/summary")
# async def stats_summary() -> dict:
#     return get_database().stats_summary()
#
#
# @router.get("/stats/series")
# async def stats_series(hours: int = 24) -> dict:
#     return {"series": get_database().stats_series(hours=hours)}
