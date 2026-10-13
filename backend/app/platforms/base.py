"""
base.py - 平台插件抽象基类与共用数据类型。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..schemas import ChatMessage


class PluginState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"  # 可用但降级（如 mock 兜底）
    UNAVAILABLE = "unavailable"


class PlatformError(Exception):
    """平台调用失败（网络/解析/风控等）。"""

    def __init__(
        self,
        message: str,
        *,
        platform: str | None = None,
        code: str = "platform_error",
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.platform = platform
        self.code = code
        self.retryable = retryable


@dataclass
class StreamDelta:
    """流式输出片段。"""

    content: str = ""
    reasoning: str = ""
    finished: bool = False
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] | None = None


@dataclass
class ChatResult:
    """非流式调用结果。"""

    content: str
    model: str
    platform: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class PlatformPlugin(ABC):
    """统一平台插件接口。

    新增平台只需实现本接口并在注册表中登记，无需改动网关编排逻辑。
    """

    #: 平台唯一标识，如 "deepseek"
    platform_id: str = "unknown"
    #: 展示名称
    display_name: str = "Unknown"
    #: 该平台支持的可请求 model 列表（对外别名）
    supported_models: list[str] = []

    @abstractmethod
    def get_models(self) -> list[str]:
        """返回该平台可用模型列表（对外 model 别名）。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        **options: Any,
    ) -> AsyncGenerator[StreamDelta, None]:
        """发送对话请求。

        始终以异步生成器形式返回；非流式场景下生成单个 finished 片段。
        调用方通过 `async for delta in plugin.chat(...)` 消费。
        """

    @abstractmethod
    def switch_model(self, model: str) -> None:
        """切换网页端模型选择器（如 Gemini Flash → Pro 变体）。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查账号/连接状态，返回是否可用。"""

    # ---- 可选钩子 ----
    def state(self) -> PluginState:
        return PluginState.READY

    def describe(self) -> dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "display_name": self.display_name,
            "models": self.get_models(),
            "state": self.state().value,
        }
