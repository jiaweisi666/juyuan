"""
web.py - 真实网页适配器（预留集成）。

通过 HTTP 调用 vendor/universal-web-api 底座已暴露的 OpenAI 兼容接口
（`{base_web_api_url}/v1/chat/completions`），由底座驱动 DrissionPage
浏览器完成网页端大模型的输入、发送与流式解析。

设计约束（对齐需求「通过插件接口扩展、不重构底座」）：
- 本适配器只做「协议适配 + 转发」，不改动底座任何逻辑；
- 底座未启动/不可达时，若开启 GATEWAY_MOCK_FALLBACK，则降级到模拟适配器，
  保证网关链路始终可用。
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from ..logging_config import get_logger
from ..schemas import ChatMessage
from .base import ChatResult, PlatformError, PlatformPlugin, PluginState, StreamDelta
from .mock import MockPlatformPlugin

logger = get_logger(__name__)


class WebPlatformPlugin(PlatformPlugin):
    """桥接 universal-web-api 底座的真实网页适配器。"""

    def __init__(self, definition: dict[str, Any], settings: Any) -> None:
        self.platform_id = definition["id"]
        self.display_name = definition.get("name", self.platform_id)
        self.supported_models = list(definition.get("models", []))
        self._definition = definition
        self._settings = settings
        self._variant = definition.get("default_variant", "default")
        self._available: bool | None = None
        self._mock = MockPlatformPlugin(definition, settings)
        self._client = httpx.AsyncClient(
            base_url=settings.base_web_api_url.rstrip("/"),
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=5.0),
        )

    # ---- 内部工具 ----
    def _base_model(self, variant: str) -> str:
        variants = self._definition.get("variants", {})
        info = variants.get(variant) or {}
        return str(info.get("base_model") or self.platform_id)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.base_web_api_key:
            headers["Authorization"] = f"Bearer {self._settings.base_web_api_key}"
        return headers

    def _payload(self, messages: list[ChatMessage], stream: bool, options: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._base_model(self._variant),
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": stream,
        }
        for key in ("temperature", "top_p", "max_tokens", "stop", "tools", "tool_choice"):
            if options.get(key) is not None:
                payload[key] = options[key]
        return payload

    # ---- PlatformPlugin ----
    def get_models(self) -> list[str]:
        return list(self.supported_models)

    def switch_model(self, model: str) -> None:
        variants = self._definition.get("variants", {})
        alias = model.split(":", 1)[1] if ":" in model else model
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
        payload = self._payload(messages, stream, options)
        start = time.perf_counter()

        try:
            if stream:
                async for delta in self._stream_chat(payload):
                    yield delta
                return
            result = await self._nonstream_chat(payload)
            result.latency_ms = int((time.perf_counter() - start) * 1000)
            yield StreamDelta(
                content=result.content,
                finished=True,
                finish_reason="stop",
                usage=result.usage,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if not self._settings.mock_fallback:
                raise PlatformError(
                    f"底座不可达: {exc}",
                    platform=self.platform_id,
                    code="base_unreachable",
                ) from exc
            logger.warning("平台 %s 底座不可达，降级到模拟适配器: %s", self.platform_id, exc)
            async for delta in self._mock.chat(messages, model, stream=stream, **options):
                yield delta
        except httpx.HTTPStatusError as exc:
            raise PlatformError(
                f"底座返回错误 {exc.response.status_code}: {exc.response.text[:200]}",
                platform=self.platform_id,
                code="base_http_error",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if not self._settings.mock_fallback:
                raise
            logger.warning("平台 %s 调用异常，降级到模拟适配器: %s", self.platform_id, exc)
            async for delta in self._mock.chat(messages, model, stream=stream, **options):
                yield delta

    async def _nonstream_chat(self, payload: dict[str, Any]) -> ChatResult:
        resp = await self._client.post(
            "/v1/chat/completions", json=payload, headers=self._headers()
        )
        resp.raise_for_status()
        data = resp.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return ChatResult(
            content=content,
            model=str(data.get("model") or payload["model"]),
            platform=self.platform_id,
            usage=usage,
            raw=data,
        )

    async def _stream_chat(self, payload: dict[str, Any]) -> AsyncGenerator[StreamDelta, None]:
        async with self._client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:") :].strip()
                if chunk == "[DONE]":
                    yield StreamDelta(finished=True, finish_reason="stop")
                    return
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                finish_reason = choice.get("finish_reason")
                piece = StreamDelta(
                    content=delta.get("content") or "",
                    reasoning=delta.get("reasoning_content") or "",
                    finish_reason=finish_reason,
                    usage=data.get("usage"),
                )
                if piece.content or piece.reasoning or finish_reason:
                    yield piece
                if finish_reason:
                    return

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/health")
            self._available = resp.status_code < 500
        except Exception:  # noqa: BLE001
            self._available = False
        return bool(self._available)

    def state(self) -> PluginState:
        if self._available is False:
            return PluginState.UNAVAILABLE
        return PluginState.READY

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        data["adapter"] = "web"
        data["current_variant"] = self._variant
        data["required"] = bool(self._definition.get("required", False))
        data["base_web_api_url"] = self._settings.base_web_api_url
        return data

    async def aclose(self) -> None:
        await self._client.aclose()
