"""
平台插件体系 - 统一的多平台 Web2API 适配接口。

对外暴露 PlatformPlugin 抽象基类、插件注册表与已注册的内置适配器。
真实网页适配器通过 HTTP 调用 vendor/universal-web-api 底座，
模拟适配器在无底座/无账号时提供可运行的降级能力。
"""

from __future__ import annotations

from .base import (
    ChatResult,
    PlatformError,
    PlatformPlugin,
    PluginState,
    StreamDelta,
)
from .registry import PlatformRegistry, get_registry
from .loader import load_platform_definitions, get_model_aliases, resolve_alias
from .mock import MockPlatformPlugin
from .web import WebPlatformPlugin

__all__ = [
    "ChatResult",
    "PlatformError",
    "PlatformPlugin",
    "PluginState",
    "StreamDelta",
    "PlatformRegistry",
    "get_registry",
    "load_platform_definitions",
    "get_model_aliases",
    "resolve_alias",
    "MockPlatformPlugin",
    "WebPlatformPlugin",
]
