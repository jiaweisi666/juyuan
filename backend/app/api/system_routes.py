"""
system_routes.py - 系统与元信息接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import get_settings
from ..platforms.registry import get_registry
from ..router.engine import get_router

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/api/gateway/info")
async def gateway_info() -> dict:
    settings = get_settings()
    registry = get_registry()
    router_engine = get_router()
    return {
        "version": __version__,
        "host": settings.host,
        "port": settings.port,
        "real_browser_enabled": settings.real_browser_enabled,
        "auto_router_enabled": settings.auto_router_enabled,
        "weights": router_engine.weights,
        "platforms": registry.describe(),
        "base_web_api_url": settings.base_web_api_url,
    }
