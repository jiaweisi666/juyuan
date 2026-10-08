"""
loader.py - 加载内置平台定义与模型别名映射（app/resources/platforms.json）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import PLATFORMS_FILE


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    if not PLATFORMS_FILE.exists():
        return {"model_aliases": {}, "platforms": []}
    with PLATFORMS_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_platform_definitions() -> list[dict[str, Any]]:
    """返回内置平台定义列表。"""
    return list(_load_raw().get("platforms", []))


def get_platform_definition(platform_id: str) -> dict[str, Any] | None:
    for item in load_platform_definitions():
        if item.get("id") == platform_id:
            return item
    return None


def get_model_aliases() -> dict[str, dict[str, Any]]:
    """返回 model 别名映射表。"""
    return dict(_load_raw().get("model_aliases", {}))


def resolve_alias(model: str) -> dict[str, Any] | None:
    """将请求 model 解析为 {platform, variant, label}；未知返回 None。"""
    aliases = get_model_aliases()
    if model in aliases:
        return aliases[model]
    return None


def reload_definitions() -> None:
    """热重载平台定义（清缓存）。"""
    _load_raw.cache_clear()
