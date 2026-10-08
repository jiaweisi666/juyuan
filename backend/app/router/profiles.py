"""
profiles.py - 模型画像管理。

为每个（平台, 变体, 任务类型）维护能力画像：准确率、平均延迟、成本、样本数。
初始值基于公开 Benchmark 的粗略设定，随后依据真实调用延迟与用户反馈在线更新。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ..logging_config import get_logger
from ..platforms.loader import load_platform_definitions
from ..storage.db import Database, get_database
from .evaluator import TaskType

logger = get_logger(__name__)

# 公开 Benchmark 粗略先验（0-1），按平台 → 任务类型
_BENCHMARK_ACCURACY: dict[str, dict[str, float]] = {
    "deepseek": {
        "code_generation": 0.92, "knowledge_qa": 0.86, "data_analysis": 0.88,
        "creative_writing": 0.80, "translation": 0.85, "general": 0.85,
    },
    "chatgpt": {
        "code_generation": 0.90, "knowledge_qa": 0.88, "data_analysis": 0.86,
        "creative_writing": 0.88, "translation": 0.86, "general": 0.87,
    },
    "claude": {
        "code_generation": 0.93, "knowledge_qa": 0.87, "data_analysis": 0.89,
        "creative_writing": 0.90, "translation": 0.87, "general": 0.88,
    },
    "kimi": {
        "code_generation": 0.84, "knowledge_qa": 0.85, "data_analysis": 0.83,
        "creative_writing": 0.82, "translation": 0.84, "general": 0.84,
    },
    "gemini": {
        "code_generation": 0.88, "knowledge_qa": 0.86, "data_analysis": 0.87,
        "creative_writing": 0.85, "translation": 0.88, "general": 0.86,
    },
    "qwen": {
        "code_generation": 0.85, "knowledge_qa": 0.84, "data_analysis": 0.84,
        "creative_writing": 0.80, "translation": 0.86, "general": 0.84,
    },
    "doubao": {
        "code_generation": 0.80, "knowledge_qa": 0.82, "data_analysis": 0.80,
        "creative_writing": 0.83, "translation": 0.82, "general": 0.82,
    },
    "glm": {
        "code_generation": 0.82, "knowledge_qa": 0.83, "data_analysis": 0.81,
        "creative_writing": 0.80, "translation": 0.83, "general": 0.82,
    },
}

# 平台 → 基线成本（相对值，越低越省钱；用于成本维度归一化）
_BASE_COST: dict[str, float] = {
    "deepseek": 0.35, "chatgpt": 0.85, "claude": 0.9, "kimi": 0.4,
    "gemini": 0.45, "qwen": 0.4, "doubao": 0.3, "glm": 0.4,
}

# 平台 → 基线延迟（ms）
_BASE_LATENCY: dict[str, float] = {
    "deepseek": 4200, "chatgpt": 5200, "claude": 4800, "kimi": 3800,
    "gemini": 4000, "qwen": 3600, "doubao": 3400, "glm": 3700,
}


class ProfileManager:
    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()
        self._lock = threading.RLock()
        self._last_refresh = 0.0
        self.ensure_seeded()

    def _default_accuracy(self, platform: str, task_type: str) -> float:
        table = _BENCHMARK_ACCURACY.get(platform, {})
        return float(table.get(task_type, table.get("general", 0.8)))

    def ensure_seeded(self) -> None:
        """为缺失的（平台, 变体, 任务类型）组合填充先验画像。"""
        with self._lock:
            for definition in load_platform_definitions():
                platform = definition["id"]
                for variant in definition.get("variants", {}):
                    for task in TaskType:
                        existing = self._db.get_profile(platform, variant, task.value)
                        if existing is None:
                            self._db.upsert_profile(
                                platform,
                                variant,
                                task_type=task.value,
                                accuracy=self._default_accuracy(platform, task.value),
                                avg_latency_ms=_BASE_LATENCY.get(platform, 4000.0),
                                cost=_BASE_COST.get(platform, 0.5),
                                samples=0,
                            )
            self._last_refresh = time.time()

    def get_accuracy(self, platform: str, variant: str, task_type: str) -> float:
        profile = self._db.get_profile(platform, variant, task_type)
        if profile is None:
            return self._default_accuracy(platform, task_type)
        return float(profile.get("accuracy") or 0.0)

    def get_latency(self, platform: str, variant: str, task_type: str) -> float:
        profile = self._db.get_profile(platform, variant, task_type)
        if profile is None:
            return _BASE_LATENCY.get(platform, 4000.0)
        return float(profile.get("avg_latency_ms") or 0.0)

    def get_cost(self, platform: str, variant: str, task_type: str) -> float:
        profile = self._db.get_profile(platform, variant, task_type)
        if profile is None:
            return _BASE_COST.get(platform, 0.5)
        return float(profile.get("cost") or 0.0)

    def record_outcome(
        self,
        platform: str,
        variant: str,
        task_type: str,
        *,
        latency_ms: int,
        success: bool,
    ) -> None:
        """记录一次真实调用结果，滑动更新平均延迟。"""
        with self._lock:
            profile = self._db.get_profile(platform, variant, task_type)
            if profile is None:
                return
            samples = int(profile.get("samples") or 0)
            prev_latency = float(profile.get("avg_latency_ms") or latency_ms)
            new_latency = (prev_latency * samples + latency_ms) / (samples + 1)
            accuracy = float(profile.get("accuracy") or 0.7)
            # 失败轻微下调准确率（作为稳定性的代理指标）
            if not success:
                accuracy = max(0.0, accuracy - 0.01)
            self._db.upsert_profile(
                platform,
                variant,
                accuracy=round(accuracy, 4),
                avg_latency_ms=round(new_latency, 1),
                samples=samples + 1,
            )

    def apply_feedback(self, platform: str, variant: str, task_type: str, rating: str) -> None:
        """依据用户点赞/点踩更新准确率（指数滑动）。"""
        with self._lock:
            profile = self._db.get_profile(platform, variant, task_type)
            if profile is None:
                return
            accuracy = float(profile.get("accuracy") or 0.7)
            delta = 0.03 if rating == "up" else -0.05
            accuracy = min(1.0, max(0.0, accuracy + delta))
            self._db.upsert_profile(platform, variant, accuracy=round(accuracy, 4))
            logger.info("反馈更新画像 %s/%s/%s -> accuracy=%.3f", platform, variant, task_type, accuracy)

    def maybe_refresh(self, interval_seconds: int) -> None:
        if time.time() - self._last_refresh >= interval_seconds:
            self.ensure_seeded()

    def snapshot(self) -> list[dict[str, Any]]:
        return self._db.list_profiles()


_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
