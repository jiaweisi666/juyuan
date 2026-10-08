"""
anthropic_routes.py - Anthropic 兼容接口。

POST /v1/messages（支持 SSE 流式），供 Claude Code / Anthropic SDK 等客户端调用。
内部复用网关编排，最终将结果转换为 Anthropic 消息格式。
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..gateway.orchestrator import GatewayUnavailableError, get_gateway
from ..schemas import (
    AnthropicRequest,
    AnthropicResponse,
    ChatCompletionRequest,
    ChatMessage,
    new_id,
)
from .deps import AuthContext, require_api_key

router = APIRouter(tags=["anthropic"])


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content or "")


def _to_internal(request: AnthropicRequest) -> ChatCompletionRequest:
    messages: list[ChatMessage] = []
    system_text = _text_from_content(request.system) if request.system else ""
    if system_text:
        messages.append(ChatMessage(role="system", content=system_text))
    for msg in request.messages:
        messages.append(ChatMessage(role=msg.role, content=_text_from_content(msg.content)))
    return ChatCompletionRequest(
        model=request.model,
        messages=messages,
        stream=request.stream,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens,
        stop=request.stop_sequences,
        tools=request.tools,
        tool_choice=request.tool_choice,
    )


@router.post("/v1/messages")
async def messages(request: AnthropicRequest, auth: AuthContext = Depends(require_api_key)):
    if not auth.allows(request.model):
        raise HTTPException(
            status_code=403,
            detail={
                "message": f"当前 API Key 无权访问模型 {request.model}",
                "type": "permission_error",
            },
        )
    gateway = get_gateway()
    internal = _to_internal(request)

    if not request.stream:
        try:
            result = await gateway.complete(internal)
        except GatewayUnavailableError as exc:
            raise HTTPException(status_code=503, detail={"message": str(exc), "type": "service_unavailable"}) from exc
        text = result.choices[0].message.content or ""
        return AnthropicResponse(
            model=result.model,
            content=[{"type": "text", "text": text}],
            stop_reason="end_turn",
            usage={
                "input_tokens": result.usage.prompt_tokens,
                "output_tokens": result.usage.completion_tokens,
            },
        )

    message_id = new_id("msg")

    async def event_stream() -> AsyncGenerator[str, None]:
        def evt(event: str, data: dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield evt("message_start", {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": request.model,
                "content": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        })
        yield evt("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        try:
            async for chunk in gateway.stream(internal):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield evt("content_block_delta", {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": delta.content},
                    })
        except GatewayUnavailableError as exc:
            yield evt("error", {"type": "error", "error": {"type": "overloaded_error", "message": str(exc)}})
        yield evt("content_block_stop", {"type": "content_block_stop", "index": 0})
        yield evt("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 0},
        })
        yield evt("message_stop", {"type": "message_stop"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
