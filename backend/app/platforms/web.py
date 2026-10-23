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
from .loader import platform_models, resolve_variant_base_model
from .mock import MockPlatformPlugin

logger = get_logger(__name__)

# 标签页 URL 命中以下片段即视为停留在登录/鉴权页（尚未完成登录）
_LOGIN_PAGE_MARKERS = ("sign_in", "signin", "sign-in", "/login", "/auth", "passport", "sso")


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
        self._health_reason = ""
        self._mock = MockPlatformPlugin(definition, settings)
        self._client = httpx.AsyncClient(
            base_url=settings.base_web_api_url.rstrip("/"),
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=5.0),
            # 底座始终监听本机回环地址，禁用环境/系统代理，避免被本机代理（如 Clash）拦截转发出 502
            trust_env=False,
        )

    # ---- 内部工具 ----
    def _base_model(self, variant: str) -> str:
        """解析变体对应的底座模型名（实时读取，兼容运行时动态发现的模型）。"""
        resolved = resolve_variant_base_model(self.platform_id, variant)
        if resolved:
            return resolved
        variants = self._definition.get("variants", {})
        info = variants.get(variant) or {}
        return str(info.get("base_model") or variant or self.platform_id)

    def _headers(self, *, force_new_conversation: bool = False) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.base_web_api_key:
            headers["Authorization"] = f"Bearer {self._settings.base_web_api_key}"
        if force_new_conversation:
            # 底座据此在网页端点击「新建对话」；仅聚元会话首轮发送，
            # 后续轮次复用同一网页对话，避免每轮都新开。
            headers["X-Juyuan-New-Conversation"] = "1"
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
        models = platform_models(self.platform_id)
        return models or list(self.supported_models)

    def switch_model(self, model: str) -> None:
        """记录当前变体；未知变体按动态模型处理（base_model 即传入的模型名）。"""
        alias = model.split(":", 1)[1] if ":" in model else model
        self._variant = alias or self._definition.get("default_variant", "default")

    _conversation_tab_index: dict[str, int] = {}

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        **options: Any,
    ) -> AsyncGenerator[StreamDelta, None]:
        conversation_id = options.pop("conversation_id", None)
        force_new_conversation = bool(options.pop("new_conversation", False))
        tab_index = None
        if conversation_id:
            tab_index = self._conversation_tab_index.get(conversation_id)

        self.switch_model(model)
        payload = self._payload(messages, stream, options)
        start = time.perf_counter()

        try:
            if stream:
                resolved_tab_index = None
                async for delta in self._stream_chat(
                    payload, tab_index=tab_index, force_new_conversation=force_new_conversation
                ):
                    if delta.finished and delta.metadata and delta.metadata.get("tab_index") is not None:
                        resolved_tab_index = delta.metadata["tab_index"]
                    yield delta
                if conversation_id and resolved_tab_index is not None:
                    self._conversation_tab_index[conversation_id] = resolved_tab_index
                return
            result, resolved_tab_index = await self._nonstream_chat(
                payload, tab_index=tab_index, force_new_conversation=force_new_conversation
            )
            result.latency_ms = int((time.perf_counter() - start) * 1000)
            if conversation_id and resolved_tab_index is not None:
                self._conversation_tab_index[conversation_id] = resolved_tab_index
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
            if tab_index and exc.response.status_code == 404:
                # 标签页可能已关闭，清除映射后回退到通用端点重试
                self._conversation_tab_index.pop(conversation_id, None)
                options["new_conversation"] = force_new_conversation
                async for delta in self.chat(messages, model, stream=stream, conversation_id=conversation_id, **options):
                    yield delta
                return
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

    async def _nonstream_chat(
        self,
        payload: dict[str, Any],
        tab_index: int | None = None,
        *,
        force_new_conversation: bool = False,
    ) -> tuple[ChatResult, int | None]:
        endpoint = f"/tab/{tab_index}/v1/chat/completions" if tab_index else "/v1/chat/completions"
        resp = await self._client.post(
            endpoint,
            json=payload,
            headers=self._headers(force_new_conversation=force_new_conversation),
        )
        resp.raise_for_status()
        data = resp.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}

        resolved_tab_index = None
        x_tab = resp.headers.get("X-Resolved-Tab-Index")
        if x_tab:
            try:
                resolved_tab_index = int(x_tab)
            except ValueError:
                pass

        return ChatResult(
            content=content,
            model=str(data.get("model") or payload["model"]),
            platform=self.platform_id,
            usage=usage,
            raw=data,
        ), resolved_tab_index

    async def _stream_chat(
        self,
        payload: dict[str, Any],
        tab_index: int | None = None,
        *,
        force_new_conversation: bool = False,
    ) -> AsyncGenerator[StreamDelta, None]:
        endpoint = f"/tab/{tab_index}/v1/chat/completions" if tab_index else "/v1/chat/completions"
        async with self._client.stream(
            "POST",
            endpoint,
            json=payload,
            headers=self._headers(force_new_conversation=force_new_conversation),
        ) as resp:
            resp.raise_for_status()

            resolved_tab_index = None
            x_tab = resp.headers.get("X-Resolved-Tab-Index")
            if x_tab:
                try:
                    resolved_tab_index = int(x_tab)
                except ValueError:
                    pass

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:") :].strip()
                if chunk == "[DONE]":
                    yield StreamDelta(
                        finished=True,
                        finish_reason="stop",
                        metadata={"tab_index": resolved_tab_index} if resolved_tab_index is not None else None,
                    )
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
                    metadata={"tab_index": resolved_tab_index} if (finish_reason and resolved_tab_index is not None) else None,
                )
                if piece.content or piece.reasoning or finish_reason:
                    yield piece
                if finish_reason:
                    return

    async def health_check(self) -> bool:
        """探测底座可达性 + 本平台标签页是否真正可用。

        仅查底座 `/health` 会把「底座在线但标签页池为空 / 标签页停在未登录页」误判为就绪，
        造成「全显示就绪但测试不可用」。这里进一步校验受控浏览器标签页池：
        需存在匹配本平台站点域名、且未停留在登录页的标签页，否则视为不可用并记录原因。
        """
        self._health_reason = ""
        try:
            resp = await self._client.get("/health", timeout=httpx.Timeout(8.0))
            if resp.status_code >= 500:
                self._available = False
                self._health_reason = f"底座健康检查异常（HTTP {resp.status_code}）"
                return False
        except Exception as exc:  # noqa: BLE001
            self._available = False
            self._health_reason = f"底座不可达：{exc}"
            return False

        host = self._site_host()
        try:
            resp = await self._client.get("/api/tab-pool/tabs", timeout=httpx.Timeout(8.0))
            resp.raise_for_status()
            tabs = (resp.json() or {}).get("tabs") or []
        except Exception as exc:  # noqa: BLE001
            self._available = False
            self._health_reason = f"查询受控浏览器标签页失败：{exc}"
            return False

        if not tabs:
            self._available = False
            self._health_reason = "受控浏览器暂无标签页，请先点击「登录导入」打开站点并完成登录"
            return False

        matched = [tab for tab in tabs if self._tab_matches(tab, host)]
        if not matched:
            self._available = False
            self._health_reason = f"未找到 {host or '本平台'} 的标签页，请先在受控浏览器打开并登录该站点"
            return False

        if all(self._is_login_page(tab) for tab in matched):
            self._available = False
            self._health_reason = f"{host} 标签页停留在登录页，请先在受控浏览器完成登录"
            return False

        self._available = True
        self._health_reason = ""
        return True

    def _site_host(self) -> str:
        """本平台站点主机名（取自 site_key / homepage），用于匹配受控浏览器标签页。"""
        raw = str(self._definition.get("site_key") or self._definition.get("homepage") or "").strip()
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        return raw.split("/", 1)[0].strip().lower()

    def _tab_matches(self, tab: dict[str, Any], host: str) -> bool:
        if not host:
            return True
        for key in ("current_domain", "route_domain", "url"):
            value = str(tab.get(key) or "").strip().lower()
            if value and host in value:
                return True
        return False

    @staticmethod
    def _is_login_page(tab: dict[str, Any]) -> bool:
        url = str(tab.get("url") or "").strip().lower()
        return any(marker in url for marker in _LOGIN_PAGE_MARKERS)

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
        data["health_reason"] = self._health_reason
        return data

    async def aclose(self) -> None:
        await self._client.aclose()
