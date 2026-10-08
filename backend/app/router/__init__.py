"""AUTO 智能路由模块。"""

from __future__ import annotations

from .evaluator import QuestionEvaluation, evaluate_question
from .profiles import ProfileManager, get_profile_manager
from .policy import RouteCandidate, WeightedPolicy
from .engine import RouterEngine, get_router

__all__ = [
    "QuestionEvaluation",
    "evaluate_question",
    "ProfileManager",
    "get_profile_manager",
    "RouteCandidate",
    "WeightedPolicy",
    "RouterEngine",
    "get_router",
]
