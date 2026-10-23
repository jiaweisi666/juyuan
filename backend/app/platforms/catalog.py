"""
catalog.py - 模型目录同步。

底座 `/v1/models` 返回的是「当前标签页实际暴露的模型名」，其中既有真正的模型名，
也有 `chat.deepseek.com` / `www.chat.deepseek.com` 这类站点标识。
本网关当前只正式支持 platforms.json 中声明的模型（DeepSeek 四个），因此：

1. 拉取底座模型列表用于连通性检查；
2. 只保留与静态配置同名的模型，站点标识一律忽略；
3. 不把底座返回的模型名写入对外模型清单，避免前端出现无用选项。
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings
from ..logging_config import get_logger
from .loader import (
    all_known_models,
    dynamic_meta,
    mark_dynamic_refreshed,
    model_owner,
    set_dynamic_models,
)

logger = get_logger(__name__)

_STATE: dict[str, Any] = {"models": [], "synced": False}


async def _fetch_base_models(timeout: float = 8.0) -> list[str]:
    settings = get_settings()
    url = settings.base_web_api_url.rstrip("/") + "/v1/models"
    headers: dict[str, str] = {}
    if settings.base_web_api_key:
        headers["Authorization"] = f"Bearer {settings.base_web_api_key}"
    # 底座监听本机回环地址，禁用环境/系统代理，避免被本机代理（如 Clash）拦截转发出 502
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [str(item.get("id")) for item in (data.get("data") or []) if item.get("id")]


async def refresh(*, force: bool = False) -> dict[str, Any]:
    """刷新动态模型目录（底座可达时）。返回状态快照。"""
    settings = get_settings()
    meta = dynamic_meta()
    now = time.time()

    if not force and meta.get("source") == "base":
        if now - float(meta.get("updated_at") or 0.0) < settings.model_cache_ttl:
            return snapshot()

    try:
        model_ids = await _fetch_base_models()
    except Exception as exc:  # noqa: BLE001
        logger.warning("拉取底座模型列表失败，沿用现有目录: %s", exc)
        mark_dynamic_refreshed(float(meta.get("updated_at") or 0.0), error=str(exc))
        return snapshot()

    # 本网关当前只正式支持 platforms.json 中声明的模型（DeepSeek 四个）。
    # 底座 /v1/models 返回的 chat.deepseek.com / deepseek / www.chat.deepseek.com
    # 是「站点标识」，不是模型，不能写入模型清单。
    known = all_known_models()
    known_lower = {str(item).lower(): str(item) for item in known}
    matched = [known_lower[str(item).lower()] for item in model_ids if str(item).lower() in known_lower]
    ignored = [item for item in model_ids if str(item).lower() not in known_lower]

    # 清掉历史遗留的动态覆盖层，确保前端永远只看到正式支持的模型
    set_dynamic_models({}, source="base")
    _STATE["models"] = [
        {"id": model, "platform": model_owner(model), "variant": ""} for model in (matched or known)
    ]
    _STATE["synced"] = True
    mark_dynamic_refreshed(now)

    if ignored:
        logger.info(
            "底座返回 %d 个模型，其中 %d 个为站点标识（已忽略）: %s",
            len(model_ids),
            len(ignored),
            ignored[:5],
        )
    logger.info("模型目录已刷新：对外仍只暴露 %d 个正式模型", len(_STATE["models"]))
    return snapshot()


def snapshot() -> dict[str, Any]:
    meta = dynamic_meta()
    source = meta.get("source", "static")
    # 同步成功后按「对外正式模型数」展示，而不是底座返回的站点标识数量
    count = len(_STATE.get("models", [])) if source == "base" else int(meta.get("count", 0) or 0)
    return {
        "source": source,
        "count": count,
        "updated_at": meta.get("updated_at", 0.0),
        "error": meta.get("error", ""),
        "models": list(_STATE.get("models", [])),
    }
