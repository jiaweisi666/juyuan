"""
engine.py - AUTO 路由引擎。

串联：问题评估 → 候选构建（含限额状态）→ 加权评分 → 决策与降级顺序 → 路由日志。
并接收调用结果与用户反馈，驱动模型画像自优化。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ..accounts.models import AccountStatus
from ..accounts.pool import KeyPool, get_pool
from ..config import get_settings
from ..logging_config import get_logger
from ..platforms.loader import load_platform_definitions, resolve_alias
from ..platforms.registry import PlatformRegistry, get_registry
from ..schemas import ChatMessage, RouteDecision
from ..storage.db import Database, get_database
from .evaluator import QuestionEvaluation, evaluate_question
from .policy import RouteCandidate, Weights, WeightedPolicy
from .profiles import ProfileManager, get_profile_manager

logger = get_logger(__name__)


class RouterEngine:
    def __init__(
        self,
        registry: PlatformRegistry | None = None,
        profiles: ProfileManager | None = None,
        pool: KeyPool | None = None,
        db: Database | None = None,
    ) -> None:
        settings = get_settings()
        self._registry = registry or get_registry()
        self._profiles = profiles or get_profile_manager()
        self._pool = pool or get_pool()
        self._db = db or get_database()
        self._policy = WeightedPolicy(
            Weights(settings.weight_accuracy, settings.weight_latency, settings.weight_cost)
        )
        self._lock = threading.RLock()
        self._bias: dict[str, float] = {}  # 反馈驱动的候选偏差

    # ---- 配置 ----
    @property
    def weights(self) -> dict[str, float]:
        w = self._policy.weights
        return {"accuracy": round(w.accuracy, 3), "latency": round(w.latency, 3), "cost": round(w.cost, 3)}

    def update_weights(self, accuracy: float, latency: float, cost: float) -> dict[str, float]:
        self._policy.update_weights(accuracy, latency, cost)
        return self.weights

    # ---- 可用性 ----
    def _platform_available(self, platform: str) -> bool:
        plugin = self._registry.get(platform)
        if plugin is None:
            return False
        accounts = self._pool.store.by_platform(platform)
        if not accounts:
            return True  # 免账号模式（模拟适配器/未配置账号）
        now = time.time()
        for account in accounts:
            if account.status == AccountStatus.INVALID:
                continue
            if account.is_cooling(now):
                continue
            return True
        return False

    def _build_candidates(self, evaluation: QuestionEvaluation) -> list[RouteCandidate]:
        candidates: list[RouteCandidate] = []
        for definition in load_platform_definitions():
            platform = definition["id"]
            plugin = self._registry.get(platform)
            if plugin is None:
                continue
            task = evaluation.task_type.value
            variants = definition.get("variants", {})
            for variant, info in variants.items():
                candidates.append(
                    RouteCandidate(
                        platform=platform,
                        variant=variant,
                        model=str(info.get("base_model") or platform),
                        label=f"{definition.get('name', platform)} {info.get('label', variant)}",
                        accuracy=self._profiles.get_accuracy(platform, variant, task),
                        latency_ms=self._profiles.get_latency(platform, variant, task),
                        cost=self._profiles.get_cost(platform, variant, task),
                        available=self._platform_available(platform) and bool(info.get("base_model")),
                        required=bool(definition.get("required", False)),
                    )
                )
        # 反馈偏差
        for candidate in candidates:
            candidate.accuracy = min(1.0, max(0.0, candidate.accuracy + self._bias.get(candidate.platform, 0.0)))
        return candidates

    # ---- 路由 ----
    def route(self, requested_model: str, messages: list[ChatMessage]) -> RouteDecision:
        settings = get_settings()
        requested = (requested_model or "auto").strip()

        if requested != "auto" and resolve_alias(requested):
            alias = resolve_alias(requested) or {}
            platform = str(alias.get("platform", ""))
            variant = str(alias.get("variant", "default"))
            decision = RouteDecision(
                requested_model=requested,
                resolved_model=self._variant_base_model(platform, variant) or requested,
                platform=platform,
                variant=variant,
                reason=f"手动指定模型 → {alias.get('label', platform)}",
                auto=False,
            )
            self._db.log_route(**decision.model_dump())
            return decision

        # AUTO：智能路由
        evaluation = evaluate_question(messages)
        if not settings.auto_router_enabled:
            decision = RouteDecision(
                requested_model=requested,
                resolved_model="deepseek-chat",
                platform="deepseek",
                variant="quick",
                reason="AUTO 路由已关闭，回退默认模型 DeepSeek",
                auto=False,
            )
            self._db.log_route(**decision.model_dump())
            return decision

        candidates = self._build_candidates(evaluation)
        ranked = self._policy.score_all(candidates)
        if not ranked:
            raise RuntimeError("无可用平台候选，请检查平台配置")

        best = ranked[0]
        reason = (
            f"任务类型={evaluation.task_type.value}, 复杂度={evaluation.complexity.value}, "
            f"预计Tokens={evaluation.estimated_tokens}, 联网={'是' if evaluation.need_web_search else '否'} | "
            f"选中 {best.platform}:{best.variant} ({self._policy.explain(best)})"
        )
        decision = RouteDecision(
            requested_model=requested,
            resolved_model=best.model,
            platform=best.platform,
            variant=best.variant,
            reason=reason,
            score=best.score,
            candidates=[
                {
                    "platform": c.platform,
                    "variant": c.variant,
                    "model": c.model,
                    "label": c.label,
                    "score": c.score,
                    "available": c.available,
                    **c.detail,
                }
                for c in ranked[:8]
            ],
            auto=True,
        )
        self._db.log_route(**decision.model_dump())
        logger.info("AUTO 路由决策: %s", reason)
        return decision

    def _variant_base_model(self, platform: str, variant: str) -> str:
        for definition in load_platform_definitions():
            if definition["id"] == platform:
                info = definition.get("variants", {}).get(variant, {})
                return str(info.get("base_model") or "")
        return ""

    # ---- 降级 ----
    def degrade_chain(self, decision: RouteDecision) -> list[dict[str, Any]]:
        """返回除首选外的候选顺序（用于限额自动降级）。"""
        return [c for c in (decision.candidates or [])][1:]

    # ---- 结果回写 ----
    def record_result(
        self, decision: RouteDecision, *, latency_ms: int, success: bool
    ) -> None:
        profiles_task = "general"
        self._profiles.record_outcome(
            decision.platform,
            decision.variant,
            profiles_task,
            latency_ms=latency_ms,
            success=success,
        )

    def apply_feedback(self, platform: str, variant: str, rating: str, task_type: str = "general") -> None:
        """用户点赞/点踩 → 更新画像，并累积平台选择偏差。"""
        self._profiles.apply_feedback(platform, variant, task_type, rating)
        with self._lock:
            delta = 0.02 if rating == "up" else -0.03
            self._bias[platform] = round(max(-0.2, min(0.2, self._bias.get(platform, 0.0) + delta)), 4)

    def refresh_profiles(self) -> None:
        self._profiles.maybe_refresh(get_settings().profile_refresh_interval)


_router: RouterEngine | None = None


def get_router() -> RouterEngine:
    global _router
    if _router is None:
        _router = RouterEngine()
    return _router
