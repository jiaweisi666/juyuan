"""
API 路由层 - 对外暴露 OpenAI / Anthropic 兼容接口与管理面板接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from .admin_routes import router as admin_router
from .anthropic_routes import router as anthropic_router
from .chat_routes import router as chat_router
from .keys_routes import router as keys_router
from .openai_routes import router as openai_router
from .system_routes import router as system_router

router = APIRouter()
router.include_router(openai_router)
router.include_router(anthropic_router)
router.include_router(system_router)
router.include_router(admin_router)
router.include_router(keys_router)
router.include_router(chat_router)

__all__ = ["router"]
