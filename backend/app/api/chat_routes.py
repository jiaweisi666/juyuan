"""
chat_routes.py - 统一对话窗口后端。

为前端对话窗口提供会话持久化（SQLite）与流式对话接口。
对话内容与第三方 API 走同一网关编排，AUTO 模式下附带路由决策说明。
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..gateway.orchestrator import get_gateway
from ..schemas import ChatCompletionRequest, ChatMessage
from ..storage.db import get_database

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ConversationCreate(BaseModel):
    title: str = "新对话"
    model: str = "auto"


class SendPayload(BaseModel):
    conversation_id: str | None = None
    model: str = "auto"
    content: str
    stream: bool = True


@router.get("/conversations")
async def list_conversations(limit: int = 100) -> dict:
    return {"conversations": get_database().list_conversations(limit=limit)}


@router.post("/conversations")
async def create_conversation(payload: ConversationCreate) -> dict:
    conv_id = get_database().create_conversation(payload.title, payload.model)
    return {"id": conv_id}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    data = get_database().get_conversation(conversation_id)
    if data is None:
        raise HTTPException(status_code=404, detail={"message": "会话不存在"})
    return data


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    get_database().delete_conversation(conversation_id)
    return {"deleted": conversation_id}


@router.post("/send")
async def send(payload: SendPayload):
    db = get_database()
    gateway = get_gateway()

    conv_id = payload.conversation_id
    if not conv_id or db.get_conversation(conv_id) is None:
        conv_id = db.create_conversation(payload.content[:24] or "新对话", payload.model)

    # 仅发送当前消息，不把历史对话作为提示词发给底座
    # （避免 deepseek 网页端每次开启新对话时重复收到完整历史）
    messages = [ChatMessage(role="user", content=payload.content)]
    db.add_message(conv_id, "user", payload.content)

    request = ChatCompletionRequest(model=payload.model, messages=messages, stream=True, conversation_id=conv_id)

    if not payload.stream:
        result = await gateway.complete(request)
        text = result.choices[0].message.content or ""
        db.add_message(conv_id, "assistant", text)
        return {
            "conversation_id": conv_id,
            "content": text,
            "route": result.juyuan_route,
        }

    async def event_stream() -> AsyncGenerator[str, None]:
        collected: list[str] = []
        route: dict = {}
        yield f"data: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
        async for chunk in gateway.stream(request):
            if chunk.juyuan_route and not route:
                route = chunk.juyuan_route
                yield f"data: {json.dumps({'route': route}, ensure_ascii=False)}\n\n"
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                collected.append(delta.content)
                yield f"data: {json.dumps({'delta': delta.content}, ensure_ascii=False)}\n\n"
        db.add_message(conv_id, "assistant", "".join(collected))
        yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
