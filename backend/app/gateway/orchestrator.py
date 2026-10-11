"""
orchestrator.py - 网关编排。

负责单次对话请求的完整链路：
路由决策 → 账号选择（KeyPool）→ 平台插件分发 → 流式解析 → 用量统计与日志落库。
对外提供流式（stream）与非流式（complete）两种入口。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

from ..accounts.pool import PoolExhaustedError, get_pool
from ..config import get_settings
from ..logging_config import get_logger
from ..platforms.base import PlatformError, StreamDelta
from ..platforms.registry import get_registry
from ..router.engine import get_router
from ..schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    RouteDecision,
    Usage,
    message_text,
    new_id,
)
from ..storage.db import get_database
from ..tool_calling import build_react_messages, parse_tool_calls

logger = get_logger(__name__)


class GatewayUnavailableError(Exception):
    def __init__(self, message: str, retry_after: int = 0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2) if text else 0


class Gateway:
    def __init__(self) -> None:
        self._registry = get_registry()
        self._router = get_router()
        self._pool = get_pool()
        self._db = get_database()
        self._settings = get_settings()

    # ---- 路由 + 账号选择 ----
    def resolve(self, request: ChatCompletionRequest) -> RouteDecision:
        return self._router.route(request.model, request.messages)

    async def _acquire(self, decision: RouteDecision):
        """获取账号占用凭证，失败时按降级链尝试次优平台。"""
        try:
            return await self._pool.acquire(decision.platform), decision
        except PoolExhaustedError as exc:
            if not decision.auto:
                raise GatewayUnavailableError(str(exc), exc.retry_after) from exc
            for candidate in self._router.degrade_chain(decision):
                if not candidate.get("available"):
                    continue
                try:
                    fallback = decision.model_copy(
                        update={
                            "platform": candidate["platform"],
                            "variant": candidate["variant"],
                            "resolved_model": candidate["model"],
                            "reason": decision.reason + f" | 降级到 {candidate['platform']}:{candidate['variant']}",
                        }
                    )
                    return await self._pool.acquire(fallback.platform), fallback
                except PoolExhaustedError:
                    continue
            raise GatewayUnavailableError(str(exc), exc.retry_after) from exc

    # ---- 主链路 ----
    async def _run(
        self,
        request: ChatCompletionRequest,
        decision: RouteDecision,
        messages: list[ChatMessage],
    ) -> AsyncGenerator[StreamDelta, None]:
        lease, decision = await self._acquire(decision)
        plugin = self._registry.get(decision.platform)
        if plugin is None:
            await self._pool.release(lease, success=False)
            raise GatewayUnavailableError(f"平台 {decision.platform} 未注册")

        model_ref = f"{decision.platform}:{decision.variant}"
        options = {
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stop": request.stop,
            "tools": request.tools,
            "tool_choice": request.tool_choice,
        }
        try:
            async for delta in plugin.chat(messages, model_ref, stream=request.stream, **options):
                yield delta
        except PlatformError:
            await self._pool.release(lease, success=False)
            raise
        else:
            await self._pool.release(lease, success=True)
        finally:
            logger.debug("调用完成 platform=%s variant=%s", decision.platform, decision.variant)

    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        decision = self.resolve(request)
        messages = request.messages
        use_tools = bool(request.tools)
        if use_tools:
            messages = build_react_messages(messages, request.tools or [])

        chunk_id = new_id("chatcmpl")
        created = int(time.time())
        start = time.perf_counter()
        first_token_ms: int | None = None
        collected: list[str] = []

        # 首块：路由信息 + assistant 角色
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=decision.resolved_model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant", content=""),
                )
            ],
            juyuan_route=decision.model_dump(),
        )

        status = "ok"
        error_msg = ""
        usage: dict[str, int] = {}
        try:
            async for delta in self._run(request, decision, messages):
                if delta.finished:
                    usage = delta.usage or usage
                    break
                if delta.reasoning:
                    yield ChatCompletionChunk(
                        id=chunk_id,
                        created=created,
                        model=decision.resolved_model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(content=delta.reasoning),
                            )
                        ],
                    )
                if delta.content:
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - start) * 1000)
                    collected.append(delta.content)
                    if not use_tools:
                        yield ChatCompletionChunk(
                            id=chunk_id,
                            created=created,
                            model=decision.resolved_model,
                            choices=[
                                ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionChunkDelta(content=delta.content),
                                )
                            ],
                        )
        except GatewayUnavailableError as exc:
            status, error_msg = "unavailable", str(exc)
            yield ChatCompletionChunk(
                id=chunk_id,
                created=created,
                model=decision.resolved_model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(content=f"\n[网关错误] {exc}"),
                        finish_reason="error",
                    )
                ],
            )
        except Exception as exc:  # noqa: BLE001
            status, error_msg = "error", str(exc)
            logger.exception("流式调用失败: %s", exc)

        full_text = "".join(collected)

        # 工具调用：缓冲解析后一次性下发
        if use_tools and full_text:
            try:
                content, tool_calls = parse_tool_calls(full_text)
            except Exception:  # noqa: BLE001
                content, tool_calls = full_text, None
            if tool_calls:
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=created,
                    model=decision.resolved_model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(
                                tool_calls=[
                                    {"index": i, **tc} for i, tc in enumerate(tool_calls)
                                ]
                            ),
                            finish_reason="tool_calls",
                        )
                    ],
                )
            else:
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=created,
                    model=decision.resolved_model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(content=content),
                        )
                    ],
                )

        total_ms = int((time.perf_counter() - start) * 1000)
        prompt_tokens = sum(_estimate_tokens(message_text(m.content)) for m in request.messages)
        completion_tokens = usage.get("completion_tokens") or _estimate_tokens(full_text)
        usage.setdefault("prompt_tokens", prompt_tokens)
        usage.setdefault("completion_tokens", completion_tokens)
        usage.setdefault("total_tokens", usage["prompt_tokens"] + usage["completion_tokens"])

        # 结束块
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=decision.resolved_model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="stop" if status == "ok" else status,
                )
            ],
        )

        self._finalize(request, decision, status, error_msg, total_ms, usage)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        decision = self.resolve(request)
        messages = request.messages
        use_tools = bool(request.tools)
        if use_tools:
            messages = build_react_messages(messages, request.tools or [])

        start = time.perf_counter()
        full_text = ""
        usage: dict[str, int] = {}
        status, error_msg = "ok", ""
        tool_calls = None
        try:
            async for delta in self._run(request, decision, messages):
                if delta.reasoning and self._settings.debug:
                    full_text += ""  # 推理内容不并入正文
                if delta.content:
                    full_text += delta.content
                if delta.finished:
                    usage = delta.usage or usage
                    break
        except GatewayUnavailableError as exc:
            status, error_msg = "unavailable", str(exc)
            raise
        except PlatformError as exc:
            status, error_msg = "error", str(exc)
            raise
        except Exception as exc:  # noqa: BLE001
            status, error_msg = "error", str(exc)
            logger.exception("非流式调用失败: %s", exc)

        total_ms = int((time.perf_counter() - start) * 1000)
        content = full_text
        if use_tools:
            content, tool_calls = parse_tool_calls(full_text)

        prompt_tokens = usage.get("prompt_tokens") or sum(
            _estimate_tokens(message_text(m.content)) for m in request.messages
        )
        completion_tokens = usage.get("completion_tokens") or _estimate_tokens(full_text)
        final_usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        self._finalize(
            request,
            decision,
            status,
            error_msg,
            total_ms,
            final_usage.model_dump(),
        )

        return ChatCompletionResponse(
            model=decision.resolved_model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=content, tool_calls=tool_calls),
                    finish_reason="tool_calls" if tool_calls else "stop",
                )
            ],
            usage=final_usage,
            juyuan_route=decision.model_dump(),
        )

    # ---- 日志与画像回写 ----
    def _finalize(
        self,
        request: ChatCompletionRequest,
        decision: RouteDecision,
        status: str,
        error_msg: str,
        latency_ms: int,
        usage: dict[str, int],
    ) -> None:
        try:
            self._db.log_call(
                requested_model=request.model,
                resolved_model=decision.resolved_model,
                platform=decision.platform,
                variant=decision.variant,
                stream=request.stream,
                status=status,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                error=error_msg,
                route_reason=decision.reason,
                auto=decision.auto,
            )
            self._router.record_result(decision, latency_ms=latency_ms, success=status == "ok")
        except Exception as exc:  # noqa: BLE001
            logger.warning("日志落库失败: %s", exc)


_gateway: Gateway | None = None


def get_gateway() -> Gateway:
    global _gateway
    if _gateway is None:
        _gateway = Gateway()
    return _gateway
