"""
policy.py - 路由策略（多目标加权评分）。

综合得分 = 准确率权重 × 0.5 + 延迟权重 × 0.2 + 成本权重 × 0.3
权重可由前端滑块调整，最终按综合得分降序作为候选与降级顺序。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteCandidate:
    platform: str
    variant: str
    model: str
    label: str = ""
    accuracy: float = 0.0          # 0-1，越高越好
    latency_ms: float = 0.0        # 毫秒，越低越好
    cost: float = 0.0              # 0-1 相对值，越低越好
    available: bool = True
    required: bool = False
    score: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Weights:
    accuracy: float = 0.5
    latency: float = 0.2
    cost: float = 0.3

    def normalized(self) -> "Weights":
        total = self.accuracy + self.latency + self.cost
        if total <= 0:
            return Weights(0.5, 0.2, 0.3)
        return Weights(self.accuracy / total, self.latency / total, self.cost / total)


class WeightedPolicy:
    def __init__(self, weights: Weights | None = None) -> None:
        self.weights = (weights or Weights()).normalized()

    def update_weights(self, accuracy: float, latency: float, cost: float) -> None:
        self.weights = Weights(accuracy, latency, cost).normalized()

    def score_all(self, candidates: list[RouteCandidate]) -> list[RouteCandidate]:
        if not candidates:
            return []
        max_latency = max((c.latency_ms for c in candidates), default=1.0) or 1.0
        max_cost = max((c.cost for c in candidates), default=1.0) or 1.0
        w = self.weights

        for candidate in candidates:
            latency_score = 1.0 - min(1.0, candidate.latency_ms / max_latency)
            cost_score = 1.0 - min(1.0, candidate.cost / max_cost)
            candidate.score = round(
                w.accuracy * candidate.accuracy
                + w.latency * latency_score
                + w.cost * cost_score,
                4,
            )
            candidate.detail = {
                "accuracy": round(candidate.accuracy, 4),
                "latency_score": round(latency_score, 4),
                "cost_score": round(cost_score, 4),
            }

        # 可用优先，其次得分降序
        return sorted(candidates, key=lambda c: (c.available, c.score), reverse=True)

    def explain(self, candidate: RouteCandidate) -> str:
        return (
            f"{candidate.platform}:{candidate.variant} "
            f"得分={candidate.score:.3f} "
            f"(准确率={candidate.detail.get('accuracy', 0):.3f}, "
            f"延迟≈{candidate.latency_ms:.0f}ms, 成本={candidate.cost:.2f})"
        )
