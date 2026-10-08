"""
pool.py - 账号智能调度（KeyPool）。

职责：
- 失效自动剔除、429/异常冷却恢复；
- 负载均衡（优先选择未达限额、调用次数最少的账号）；
- 单账号 RPM 限流（滑动 60s 窗口）；
- 请求间随机延迟（模拟人类节奏）；
- 全局并发上限；
- 全部账号不可用时返回明确错误与预计恢复时间。
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass

from ..config import get_settings
from ..logging_config import get_logger
from .models import Account, AccountStatus
from .store import AccountStore

logger = get_logger(__name__)

RPM_WINDOW_SECONDS = 60.0


class PoolExhaustedError(Exception):
    """所有账号均不可用。"""

    def __init__(self, platform: str, retry_after: int, reason: str) -> None:
        super().__init__(f"平台 {platform} 无可用账号: {reason}")
        self.platform = platform
        self.retry_after = retry_after
        self.reason = reason


@dataclass
class AccountLease:
    """一次调用的账号占用凭证（异步上下文管理器）。"""

    pool: "KeyPool"
    account: Account | None
    platform: str
    _released: bool = False

    async def __aenter__(self) -> "AccountLease":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.pool.release(self, success=exc_type is None)
        return False


class KeyPool:
    def __init__(self, store: AccountStore | None = None) -> None:
        self._settings = get_settings()
        self._store = store or AccountStore()
        self._rpm_history: dict[str, deque[float]] = {}
        self._sem = asyncio.Semaphore(max(1, self._settings.max_concurrency))
        self._lock = asyncio.Lock()

    # ---- RPM ----
    def _prune_rpm(self, account_id: str, now: float) -> deque[float]:
        history = self._rpm_history.setdefault(account_id, deque())
        while history and now - history[0] > RPM_WINDOW_SECONDS:
            history.popleft()
        return history

    def _rpm_available(self, account_id: str, now: float) -> tuple[bool, float]:
        history = self._prune_rpm(account_id, now)
        if len(history) < self._settings.account_rpm:
            return True, 0.0
        wait = RPM_WINDOW_SECONDS - (now - history[0])
        return False, max(0.0, wait)

    def _record_rpm(self, account_id: str) -> None:
        now = time.time()
        self._prune_rpm(account_id, now).append(now)

    # ---- 选择 ----
    def _pick_available(self, platform: str) -> tuple[Account | None, float, str]:
        """返回 (账号, 预计等待秒, 原因)。账号为 None 表示无可用。"""
        now = time.time()
        candidates = self._store.by_platform(platform)
        if not candidates:
            return None, 0.0, "no_account"

        best: Account | None = None
        best_calls = None
        min_wait = float("inf")
        reason = "cooldown"

        for account in candidates:
            if account.status == AccountStatus.INVALID:
                continue
            if account.is_cooling(now):
                min_wait = min(min_wait, account.cooldown_until - now)
                continue
            ok, wait = self._rpm_available(account.id, now)
            if not ok:
                min_wait = min(min_wait, wait)
                reason = "rpm_limit"
                continue
            # 负载均衡：优先调用次数最少
            if best is None or account.call_count < (best_calls or 0):
                best = account
                best_calls = account.call_count
        return best, (0.0 if best else min_wait), reason

    async def acquire(self, platform: str) -> AccountLease:
        """获取一个可用账号占用凭证；必要时等待/限流。"""
        await self._sem.acquire()
        try:
            async with self._lock:
                account, wait, reason = self._pick_available(platform)
            if account is None and reason == "no_account":
                # 未配置账号：以“免账号”模式放行（模拟适配器/本地演示可跑通链路）
                return AccountLease(self, None, platform)
            if account is None:
                raise PoolExhaustedError(platform, int(wait) + 1, reason)

            self._record_rpm(account.id)
            # 随机人类节奏延迟
            delay = random.uniform(
                self._settings.min_delay_seconds, self._settings.max_delay_seconds
            )
            if delay > 0:
                await asyncio.sleep(delay)
            return AccountLease(self, account, platform)
        except Exception:
            self._sem.release()
            raise

    async def release(self, lease: AccountLease, *, success: bool) -> None:
        if lease._released:
            return
        lease._released = True
        if lease.account is not None:
            self._store.mark_result(
                lease.account.id,
                success=success,
                cooldown_seconds=0 if success else self._settings.cooldown_seconds,
            )
        self._sem.release()

    # ---- 统计 ----
    def status(self) -> dict[str, int]:
        accounts = self._store.all()
        return {
            "total": len(accounts),
            "active": sum(1 for a in accounts if a.status == AccountStatus.ACTIVE),
            "cooldown": sum(1 for a in accounts if a.status == AccountStatus.COOLDOWN),
            "invalid": sum(1 for a in accounts if a.status == AccountStatus.INVALID),
        }

    @property
    def store(self) -> AccountStore:
        return self._store


_pool: KeyPool | None = None


def get_pool() -> KeyPool:
    global _pool
    if _pool is None:
        _pool = KeyPool()
    return _pool
