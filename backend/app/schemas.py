"""
schemas.py - 对外数据模型

定义 OpenAI 兼容（/v1/chat/completions、/v1/models）与 Anthropic 兼容（/v1/messages）
的请求/响应模型，以及内部共用的消息结构。所有对外 JSON 均由这些模型序列化。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# 通用
# --------------------------------------------------------------------------- #
Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    """内部统一消息结构（OpenAI 风格）。

    content 兼容两种形态：纯字符串，或 OpenAI 多模态数组
    （如 ``[{"type": "text", ...}, {"type": "image_url", ...}]``）。
    数组形态会原样透传给底座（底座支持图片/音频/视频片段），
    需要纯文本的场景请改用 message_text()。
    """

    role: Role
    content: str | list[dict[str, Any]] | None = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


def message_text(content: Any) -> str:
    """把消息 content 规整为纯文本，兼容 OpenAI 多模态数组。

    文本片段直接保留；图片/音频/视频等非文本片段以占位符表示，
    避免多模态输入在 token 估算、任务分类等纯文本环节被误处理。
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "").strip().lower()
            if block_type in {"image_url", "input_image", "output_image"}:
                parts.append("[图片]")
            elif block_type in {"audio_url", "input_audio", "output_audio"}:
                parts.append("[音频]")
            elif block_type in {"video_url", "input_video", "output_video"}:
                parts.append("[视频]")
            elif block.get("text"):
                parts.append(str(block["text"]))
        return "\n".join(part for part in parts if part)
    return str(content)


def new_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def now_ts() -> int:
    return int(time.time())


# --------------------------------------------------------------------------- #
# OpenAI 请求
# --------------------------------------------------------------------------- #
class ChatCompletionRequest(BaseModel):
    """OpenAI /v1/chat/completions 请求体。"""

    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    user: str | None = None

    model_config = {"extra": "allow"}


# --------------------------------------------------------------------------- #
# OpenAI 响应
# --------------------------------------------------------------------------- #
class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: new_id("chatcmpl"))
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=now_ts)
    model: str = "auto"
    choices: list[ChatCompletionChoice] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    # 非标准扩展：AUTO 路由决策说明
    juyuan_route: dict[str, Any] | None = None


class ChatCompletionChunkDelta(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=now_ts)
    model: str = "auto"
    choices: list[ChatCompletionChunkChoice] = Field(default_factory=list)
    juyuan_route: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# OpenAI /v1/models
# --------------------------------------------------------------------------- #
class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=now_ts)
    owned_by: str = "juyuan"


class ModelsResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Anthropic /v1/messages
# --------------------------------------------------------------------------- #
class AnthropicMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Any  # str 或 [{type:"text", text:"..."}]


class AnthropicRequest(BaseModel):
    model: str = "auto"
    messages: list[AnthropicMessage]
    system: str | list[dict[str, Any]] | None = None
    max_tokens: int = 4096
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    stop_sequences: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None

    model_config = {"extra": "allow"}


class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicContentBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = ""


class AnthropicResponse(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msg"))
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str = "auto"
    content: list[AnthropicContentBlock] = Field(default_factory=list)
    stop_reason: str | None = "end_turn"
    stop_sequence: str | None = None
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)


# --------------------------------------------------------------------------- #
# 错误
# --------------------------------------------------------------------------- #
class ErrorDetail(BaseModel):
    message: str
    type: str = "invalid_request_error"
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --------------------------------------------------------------------------- #
# 内部：路由决策
# --------------------------------------------------------------------------- #
class RouteDecision(BaseModel):
    """AUTO 路由（或手动映射）的决策结果。"""

    requested_model: str
    resolved_model: str
    platform: str
    variant: str
    reason: str = ""
    score: float | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    auto: bool = False
