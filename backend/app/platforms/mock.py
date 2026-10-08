"""
mock.py - 模拟平台适配器。

在未启用真实浏览器（或真实底座不可用）时，提供可运行的降级实现：
以确定性方式生成一段结构化回复并逐字流式输出，使整条链路
（鉴权 → 路由 → 账号池 → 插件分发 → SSE 流式返回）可端到端跑通。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from ..schemas import ChatMessage
from .base import ChatResult, PlatformPlugin, PluginState, StreamDelta


def _last_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return ""


def _build_reply(platform: str, variant: str, user_text: str) -> str:
    preview = user_text.strip().replace("\n", " ")
    if len(preview) > 120:
        preview = preview[:120] + "…"
    return (
        f"[{platform}:{variant} 模拟响应]\n\n"
        f"已收到你的输入：{preview or '（空）'}\n\n"
        "这是模拟适配器生成的回复，用于验证网关链路。\n"
        "启用真实浏览器适配器（GATEWAY_REAL_BROWSER_ENABLED=true）后，"
        "请求将由 universal-web-api 底座驱动网页端大模型产生真实回答。"
    )


class MockPlatformPlugin(PlatformPlugin):
    """确定性的模拟适配器，不依赖网络与浏览器。"""

    def __init__(self, definition: dict[str, Any], settings: Any) -> None:
        self.platform_id = definition["id"]
        self.display_name = definition.get("name", self.platform_id)
        self.supported_models = list(definition.get("models", []))
        self._definition = definition
        self._settings = settings
        self._variant = definition.get("default_variant", "default")
        self._chunk_delay = max(0.0, float(settings.min_delay_seconds) * 0.01)

    # ---- PlatformPlugin ----
    def get_models(self) -> list[str]:
        return list(self.supported_models)

    def switch_model(self, model: str) -> None:
        variants = self._definition.get("variants", {})
        alias = model
        if ":" in model:
            alias = model.split(":", 1)[1]
        if alias in variants:
            self._variant = alias
        else:
            self._variant = self._definition.get("default_variant", "default")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        **options: Any,
    ) -> AsyncGenerator[StreamDelta, None]:
        self.switch_model(model)
        text = _build_reply(self.platform_id, self._variant, _last_user_text(messages))
        completion_tokens = max(1, len(text) // 2)

        if not stream:
            yield StreamDelta(
                content=text,
                finished=True,
                finish_reason="stop",
                usage={
                    "prompt_tokens": sum(len(m.content or "") for m in messages) // 2,
                    "completion_tokens": completion_tokens,
                },
            )
            return

        step = 6
        for i in range(0, len(text), step):
            if self._chunk_delay:
                await asyncio.sleep(self._chunk_delay)
            yield StreamDelta(content=text[i : i + step])

        yield StreamDelta(
            finished=True,
            finish_reason="stop",
            usage={
                "prompt_tokens": sum(len(m.content or "") for m in messages) // 2,
                "completion_tokens": completion_tokens,
            },
        )

    async def health_check(self) -> bool:
        return True

    def state(self) -> PluginState:
        return PluginState.DEGRADED

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        data["adapter"] = "mock"
        data["current_variant"] = self._variant
        data["required"] = bool(self._definition.get("required", False))
        return data
