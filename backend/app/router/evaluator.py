"""
evaluator.py - 问题评估（规则版）。

对用户输入做多维度评估：任务类型、复杂度、预计 Token 消耗、是否需要联网搜索。
初期基于关键词与长度判断，后续可替换为轻量分类模型。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from ..schemas import ChatMessage


class TaskType(str, Enum):
    KNOWLEDGE_QA = "knowledge_qa"
    CODE_GENERATION = "code_generation"
    CREATIVE_WRITING = "creative_writing"
    DATA_ANALYSIS = "data_analysis"
    TRANSLATION = "translation"
    GENERAL = "general"


class Complexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


_KEYWORDS: dict[TaskType, tuple[str, ...]] = {
    TaskType.CODE_GENERATION: (
        "代码", "函数", "报错", "bug", "调试", "算法", "python", "javascript", "java",
        "sql", "接口", "脚本", "实现", "重构", "单元测试", "code", "debug", "error",
        "traceback", "编译", "依赖",
    ),
    TaskType.DATA_ANALYSIS: (
        "分析", "统计", "数据", "趋势", "图表", "报表", "对比", "指标", "预测",
        "回归", "相关性", "数据集", "excel", "pandas", "analysis", "benchmark",
    ),
    TaskType.CREATIVE_WRITING: (
        "写一篇", "写一个故事", "文案", "创意", "小说", "诗歌", "剧本", "广告语",
        "宣传", "润色", "改写", "起名", "slogan", "story", "poem", "essay",
    ),
    TaskType.TRANSLATION: (
        "翻译", "translate", "译成", "英文版", "中文版", "英译中", "中译英", "本地化",
    ),
    TaskType.KNOWLEDGE_QA: (
        "什么是", "是什么", "为什么", "如何", "怎么", "解释", "介绍一下", "原理",
        "定义", "区别", "what is", "why", "how to", "explain",
    ),
}

_WEB_SEARCH_HINTS = (
    "最新", "今天", "昨天", "本周", "实时", "新闻", "现价", "股价", "汇率", "天气",
    "2025", "2026", "刚刚", "目前", "现在", "latest", "today", "current", "news",
    "realtime",
)

_REASONING_HINTS = (
    "证明", "推理", "详细分析", "逐步", "一步一步", "论证", "推导", "优化方案",
    "架构设计", "方案设计", "深度", "对比分析", "step by step", "prove",
)


@dataclass
class QuestionEvaluation:
    task_type: TaskType
    complexity: Complexity
    estimated_tokens: int
    need_web_search: bool
    text_length: int
    signals: list[str] = field(default_factory=list)


def _collect_text(messages: list[ChatMessage]) -> str:
    parts = [m.content or "" for m in messages if m.role in ("user", "system")]
    return "\n".join(parts).strip()


def _classify_task(text: str) -> tuple[TaskType, list[str]]:
    lowered = text.lower()
    scores: dict[TaskType, int] = {}
    signals: list[str] = []
    for task, keywords in _KEYWORDS.items():
        hits = [kw for kw in keywords if kw in lowered]
        if hits:
            scores[task] = len(hits)
            signals.extend(hits[:3])
    if not scores:
        return TaskType.GENERAL, signals
    best = max(scores, key=lambda k: scores[k])
    return best, signals


def _estimate_complexity(text: str, task: TaskType) -> Complexity:
    length = len(text)
    lowered = text.lower()
    reasoning = any(h in lowered for h in _REASONING_HINTS)
    if length > 600 or reasoning or task in (TaskType.CODE_GENERATION, TaskType.DATA_ANALYSIS):
        if length > 1200 or reasoning:
            return Complexity.COMPLEX
        return Complexity.MEDIUM
    if length > 200:
        return Complexity.MEDIUM
    return Complexity.SIMPLE


def _estimate_tokens(text: str, complexity: Complexity) -> int:
    # 粗略估算：中文按字符、英文按词；输出预期随复杂度放大
    base = max(1, len(text) // 2)
    factor = {Complexity.SIMPLE: 1.5, Complexity.MEDIUM: 2.5, Complexity.COMPLEX: 4.0}[complexity]
    return int(base * factor)


def evaluate_question(messages: list[ChatMessage]) -> QuestionEvaluation:
    text = _collect_text(messages)
    task_type, signals = _classify_task(text)
    complexity = _estimate_complexity(text, task_type)
    need_web = any(h in text.lower() for h in _WEB_SEARCH_HINTS)
    if need_web:
        signals.append("需要联网")
    return QuestionEvaluation(
        task_type=task_type,
        complexity=complexity,
        estimated_tokens=_estimate_tokens(text, complexity),
        need_web_search=need_web,
        text_length=len(text),
        signals=signals,
    )
