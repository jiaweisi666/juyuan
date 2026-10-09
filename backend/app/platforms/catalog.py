"""
catalog.py - 动态模型目录。

真实网页适配器接入底座后，底座 `/v1/models` 会返回「当前标签页实际暴露的模型名」。
本模块负责：

1. 拉取底座模型列表（带 TTL 缓存，默认 10 分钟）；
2. 将模型名归因到网关内置平台（精确匹配 base_model → 平台默认变体 → 关键词启发式）；
3. 写入 loader 的动态覆盖层，使 `/v1/models`、AUTO 路由候选与网页端模型选择
   随网页端迭代自动跟进，无需修改代码或配置文件。

底座不可达时保留上一次成功结果；从未成功则回退到 platforms.json 的静态定义。
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings
from ..logging_config import get_logger
from .loader import (
    dynamic_meta,
    load_platform_definitions,
    mark_dynamic_refreshed,
    set_dynamic_models,
)

logger = get_logger(__name__)

# 平台关键词提示：把无法精确匹配的模型名归因到最可能的平台
PLATFORM_HINTS: dict[str, list[str]] = {
    "deepseek": ["deepseek"],
    "chatgpt": ["chatgpt", "gpt", "openai", "o1", "o3", "o4"],
    "claude": ["claude", "anthropic"],
    "kimi": ["kimi", "moonshot"],
    "gemini": ["gemini", "bard"],
    "qwen": ["qwen", "tongyi", "通义"],
    "doubao": ["doubao", "豆包", "skylark"],
    "glm": ["glm", "chatglm", "zhipu", "智谱"],
}

# 底座在「尚无任何已打开站点」时返回的通用占位模型名（不含真实平台信息）
_GENERIC_BASE_MODELS = {"web-browser"}

_STATE: dict[str, Any] = {"models": [], "synced": False}


def _slug(model_id: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in model_id).strip("-").lower()
    return slug or "model"


def _match_platform(model_id: str, definitions: list[dict[str, Any]]) -> tuple[str, str, bool] | None:
    """把模型名归因到 (platform_id, variant, 是否为新增变体)。"""
    low = model_id.lower()

    # 1) 精确命中某变体的 base_model
    for definition in definitions:
        for variant, info in definition.get("variants", {}).items():
            if str(info.get("base_model") or "").lower() == low:
                return definition["id"], variant, False

    # 2) 命中平台 models 清单 → 使用平台默认变体
    for definition in definitions:
        if low in [str(m).lower() for m in definition.get("models", [])]:
            return definition["id"], str(definition.get("default_variant", "default")), False

    # 3) 关键词启发式 → 新增变体（变体名取模型名 slug，底座模型名即 base_model）
    for definition in definitions:
        pid = definition["id"]
        hints = list(PLATFORM_HINTS.get(pid, [])) + [pid]
        for hint in hints:
            if hint and hint in low:
                return pid, _slug(model_id), True
    return None


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

    definitions = load_platform_definitions()
    platforms: dict[str, dict[str, Any]] = {}
    resolved: list[dict[str, str]] = []
    for model_id in model_ids:
        hit = _match_platform(model_id, definitions)
        if hit is None:
            continue
        platform_id, variant, is_new = hit
        entry = platforms.setdefault(platform_id, {"variants": {}, "models": []})
        if model_id not in entry["models"]:
            entry["models"].append(model_id)
        if is_new:
            entry["variants"][variant] = {"label": model_id, "kind": "chat", "base_model": model_id}
        resolved.append({"id": model_id, "platform": platform_id, "variant": variant})

    if not platforms:
        if not model_ids:
            reason = "底座未返回任何模型"
        elif set(model_ids) <= _GENERIC_BASE_MODELS:
            # 底座仅返回通用占位（如 web-browser），说明受控浏览器里还没有已打开/已登录的站点
            reason = "底座暂无已打开站点的模型，请先「登录导入」打开并登录站点后再同步"
        else:
            reason = f"底座返回的 {len(model_ids)} 个模型均无法归因到已接入平台"
        mark_dynamic_refreshed(now, error=reason)
        logger.warning("底座返回 %d 个模型，但未能归因到任何平台: %s", len(model_ids), model_ids[:5])
        return snapshot()

    set_dynamic_models(platforms)
    mark_dynamic_refreshed(now)
    _STATE["models"] = resolved
    _STATE["synced"] = True
    logger.info("动态模型目录已刷新：%d 个模型（来源：底座 /v1/models）", len(resolved))
    return snapshot()


def snapshot() -> dict[str, Any]:
    meta = dynamic_meta()
    return {
        "source": meta.get("source", "static"),
        "count": meta.get("count", 0),
        "updated_at": meta.get("updated_at", 0.0),
        "error": meta.get("error", ""),
        "models": list(_STATE.get("models", [])),
    }
