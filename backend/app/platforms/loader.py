"""
loader.py - 加载内置平台定义与模型别名映射（app/resources/platforms.json）。

除静态配置外，本模块还支持一份「运行时动态覆盖层」：真实网页适配器接入底座
后，底座 `/v1/models` 暴露的模型名会通过 `set_dynamic_models()` 写入覆盖层，
从而让模型列表、AUTO 路由候选与网页端模型选择随网页端迭代自动跟进，无需改代码。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import PLATFORMS_FILE

# 运行时动态覆盖层：{platform_id: {"variants": {variant: info}, "models": [model_id]}}
_DYNAMIC: dict[str, dict[str, Any]] = {}
_DYNAMIC_META: dict[str, Any] = {"source": "static", "updated_at": 0.0, "count": 0, "error": ""}


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    if not PLATFORMS_FILE.exists():
        return {"model_aliases": {}, "platforms": []}
    with PLATFORMS_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_platform_definitions() -> list[dict[str, Any]]:
    """返回内置平台定义列表（已合并运行时动态覆盖层）。"""
    raw = list(_load_raw().get("platforms", []))
    if not _DYNAMIC:
        return raw

    merged: list[dict[str, Any]] = []
    for definition in raw:
        overlay = _DYNAMIC.get(definition["id"])
        if not overlay:
            merged.append(definition)
            continue
        item = dict(definition)
        variants = dict(definition.get("variants", {}))
        for variant, info in overlay.get("variants", {}).items():
            variants.setdefault(variant, info)
        item["variants"] = variants
        # 只暴露 platforms.json 中正式声明的模型。
        # 底座 /v1/models 会返回 chat.deepseek.com / www.chat.deepseek.com 这类「站点名」，
        # 它们不是可调用模型，不能混入前端的模型清单。
        item["models"] = list(definition.get("models", []))
        merged.append(item)
    return merged


def get_platform_definition(platform_id: str) -> dict[str, Any] | None:
    for item in load_platform_definitions():
        if item.get("id") == platform_id:
            return item
    return None


def get_model_aliases() -> dict[str, dict[str, Any]]:
    """返回 model 别名映射表。"""
    return dict(_load_raw().get("model_aliases", {}))


def resolve_alias(model: str) -> dict[str, Any] | None:
    """将请求 model 解析为 {platform, variant, label}；未知返回 None。

    静态别名优先；未命中时回退到「按 variants.base_model 反查」，
    以支持运行时从底座动态发现的模型。
    """
    aliases = get_model_aliases()
    if model in aliases:
        return aliases[model]
    for definition in load_platform_definitions():
        for variant, info in definition.get("variants", {}).items():
            if str(info.get("base_model") or "") == model:
                return {
                    "platform": definition["id"],
                    "variant": variant,
                    "label": f"{definition.get('name', definition['id'])} {info.get('label', variant)}",
                }
    return None


def resolve_variant_base_model(platform_id: str, variant: str) -> str:
    """解析平台变体对应的底座模型名（实时读取，含动态覆盖）。"""
    definition = get_platform_definition(platform_id)
    if not definition:
        return ""
    info = definition.get("variants", {}).get(variant) or {}
    return str(info.get("base_model") or "")


def platform_models(platform_id: str) -> list[str]:
    """返回平台当前可用模型列表（静态 + 动态覆盖）。"""
    definition = get_platform_definition(platform_id)
    return list(definition.get("models", [])) if definition else []


def all_known_models() -> list[str]:
    """返回全部对外可请求的模型名（不含 auto）。"""
    seen: list[str] = []
    for definition in load_platform_definitions():
        for model in definition.get("models", []):
            if model not in seen:
                seen.append(model)
    return seen


def model_owner(model: str) -> str:
    """返回模型归属的平台 id（用于 /v1/models 的 owned_by）。"""
    alias = resolve_alias(model)
    if alias and alias.get("platform"):
        return str(alias["platform"])
    return "juyuan"


def set_dynamic_models(platforms: dict[str, dict[str, Any]], *, source: str = "base") -> None:
    """写入运行时动态覆盖层（由 catalog 模块在发现底座模型后调用）。"""
    _DYNAMIC.clear()
    for platform_id, overlay in platforms.items():
        _DYNAMIC[platform_id] = {
            "variants": dict(overlay.get("variants", {})),
            "models": list(overlay.get("models", [])),
        }
    _DYNAMIC_META.update(
        {
            "source": source,
            "count": sum(len(v.get("models", [])) for v in platforms.values()),
        }
    )


def clear_dynamic_models() -> None:
    """清空动态覆盖层，回到静态配置。"""
    _DYNAMIC.clear()
    _DYNAMIC_META.update({"source": "static", "count": 0})


def dynamic_meta() -> dict[str, Any]:
    """返回动态覆盖层元信息（来源 / 数量 / 更新时间）。"""
    return dict(_DYNAMIC_META)


def mark_dynamic_refreshed(updated_at: float, *, error: str = "") -> None:
    """记录动态目录最近一次刷新时间与错误信息。"""
    _DYNAMIC_META["updated_at"] = updated_at
    _DYNAMIC_META["error"] = error


def reload_definitions() -> None:
    """热重载静态平台定义（清缓存），不清除动态覆盖层。"""
    _load_raw.cache_clear()
