"""
openai_routes.py - OpenAI 兼容接口。

- POST /v1/chat/completions（支持 SSE 流式）
- GET  /v1/models
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..gateway.orchestrator import GatewayUnavailableError, get_gateway
from ..platforms.loader import all_known_models, model_owner
from ..schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelsResponse,
)
from .deps import AuthContext, require_api_key

router = APIRouter(tags=["openai"])


def _sse(data: str) -> str:
    return f"data: {data}\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    auth: AuthContext = Depends(require_api_key),
):
    if not auth.allows(request.model):
        raise HTTPException(
            status_code=403,
            detail={
                "message": f"当前 API Key 无权访问模型 {request.model}",
                "type": "permission_error",
            },
        )
    gateway = get_gateway()

    if not request.stream:
        try:
            response: ChatCompletionResponse = await gateway.complete(request)
        except GatewayUnavailableError as exc:
            raise HTTPException(status_code=503, detail={"message": str(exc), "type": "service_unavailable"}) from exc
        return response

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in gateway.stream(request):
                yield _sse(chunk.model_dump_json(exclude_none=True))
        except GatewayUnavailableError as exc:
            yield _sse(json.dumps({"error": {"message": str(exc), "type": "service_unavailable"}}, ensure_ascii=False))
        yield _sse("[DONE]")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/v1/models")
async def list_models(auth: AuthContext = Depends(require_api_key)) -> ModelsResponse:
    cards: list[ModelCard] = []
    for model in all_known_models():
        if not auth.allows(model):
            continue
        cards.append(ModelCard(id=model, owned_by=model_owner(model)))
    return ModelsResponse(data=cards)
