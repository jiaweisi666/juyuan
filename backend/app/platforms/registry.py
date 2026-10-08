"""
registry.py - 平台插件注册表。

网关在启动时根据平台定义与运行配置，为每个平台实例化对应的适配器
（真实网页适配器或模拟适配器）并登记；AUTO 路由与网关编排通过注册表按
platform_id 取用插件。
"""

from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..logging_config import get_logger
from .base import PlatformPlugin
from .loader import load_platform_definitions

logger = get_logger(__name__)


class PlatformRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PlatformPlugin] = {}

    def register(self, plugin: PlatformPlugin) -> None:
        self._plugins[plugin.platform_id] = plugin

    def get(self, platform_id: str) -> PlatformPlugin | None:
        return self._plugins.get(platform_id)

    def all(self) -> list[PlatformPlugin]:
        return list(self._plugins.values())

    def ids(self) -> list[str]:
        return list(self._plugins.keys())

    def describe(self) -> list[dict[str, Any]]:
        return [p.describe() for p in self._plugins.values()]

    def build(self) -> None:
        """根据平台定义与配置构建内置插件。"""
        settings = get_settings()
        definitions = load_platform_definitions()

        # 延迟导入避免循环依赖
        from .mock import MockPlatformPlugin
        from .web import WebPlatformPlugin

        for definition in definitions:
            platform_id = definition["id"]
            if settings.real_browser_enabled:
                plugin: PlatformPlugin = WebPlatformPlugin(definition, settings)
            else:
                plugin = MockPlatformPlugin(definition, settings)
            self.register(plugin)

        logger.info(
            "已注册 %d 个平台插件: %s (real_browser=%s)",
            len(self._plugins),
            ", ".join(self.ids()),
            settings.real_browser_enabled,
        )


_registry: PlatformRegistry | None = None


def get_registry() -> PlatformRegistry:
    global _registry
    if _registry is None:
        _registry = PlatformRegistry()
        _registry.build()
    return _registry
