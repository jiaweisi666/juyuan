"""
tool_calling.py - 服务端模拟的工具调用（ReAct 格式）。

网页端大模型无原生函数调用能力，这里通过注入 ReAct 指令约束输出格式，
再在服务端解析为 OpenAI 兼容的 tool_calls，从而实现 Tool Calling 兼容层。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .logging_config import get_logger
from .schemas import ChatMessage

logger = get_logger(__name__)

REACT_INSTRUCTION = """你是一个支持工具调用的助手。你可以在需要时调用下列工具来回答用户问题。

可用工具：
{tools}

调用工具时，请严格按以下格式输出（每次只调用一个工具）：

Thought: 你的思考
Action: 工具名称
Action Input: {{"参数名": "参数值"}}

当你已经可以回答用户时，请直接输出最终答案，并以 "Final Answer:" 开头。
"""

_ACTION_RE = re.compile(r"Action\s*[:：]\s*(.+)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(r"Action\s*Input\s*[:：]\s*(\{.*\})", re.IGNORECASE | re.DOTALL)
_FINAL_RE = re.compile(r"Final\s*Answer\s*[:：]\s*(.+)", re.IGNORECASE | re.DOTALL)


def _format_tools(tools: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for tool in tools:
        fn = tool.get("function", tool) if isinstance(tool, dict) else {}
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        lines.append(f"- {name}: {desc}\n  参数 schema: {json.dumps(params, ensure_ascii=False)}")
    return "\n".join(lines) if lines else "（无）"


def build_react_messages(
    messages: list[ChatMessage], tools: list[dict[str, Any]]
) -> list[ChatMessage]:
    """在消息头部注入 ReAct 工具说明。"""
    instruction = REACT_INSTRUCTION.format(tools=_format_tools(tools))
    augmented = [ChatMessage(role="system", content=instruction)]
    augmented.extend(messages)
    return augmented


def _tool_call(name: str, arguments: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def parse_tool_calls(text: str) -> tuple[str, list[dict[str, Any]] | None]:
    """从模型输出中解析工具调用。

    返回 (剩余文本内容, tool_calls 或 None)。
    支持两种格式：OpenAI 风格 JSON 块 / ReAct 的 Action + Action Input。
    """
    if not text:
        return text, None

    # 1) OpenAI 风格：{"tool_calls": [...]}
    try:
        stripped = text.strip()
        if stripped.startswith("{") and "tool_calls" in stripped:
            data = json.loads(stripped)
            calls = data.get("tool_calls")
            if isinstance(calls, list) and calls:
                normalized = []
                for idx, call in enumerate(calls):
                    fn = call.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"raw": args}
                    normalized.append(
                        _tool_call(fn.get("name", "unknown"), args, f"call_{idx}")
                    )
                return "", normalized
    except (json.JSONDecodeError, AttributeError):
        pass

    # 2) ReAct 格式
    action_match = _ACTION_RE.search(text)
    if action_match:
        name = action_match.group(1).strip().split("\n")[0].strip()
        input_match = _ACTION_INPUT_RE.search(text)
        arguments: dict[str, Any] = {}
        if input_match:
            try:
                arguments = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                arguments = {"raw": input_match.group(1)}
        content = ""
        final_match = _FINAL_RE.search(text)
        if final_match:
            content = final_match.group(1).strip()
        return content, [_tool_call(name, arguments, "call_0")]

    return text, None
