"""
models.py - 账号数据模型。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AccountStatus(str, Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    INVALID = "invalid"
    LIMITED = "limited"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Account:
    """单个平台账号。

    敏感字段（session_key / cookies）以密文形式存储，运行时按需解密。
    """

    id: str = field(default_factory=_new_id)
    platform: str = ""
    email: str = ""
    remark: str = ""

    # 加密字段（密文）
    session_key_enc: str = ""
    cookies_enc: str = ""

    status: AccountStatus = AccountStatus.ACTIVE
    call_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0
    created_at: float = field(default_factory=time.time)

    def is_cooling(self, now: float | None = None) -> bool:
        now = now or time.time()
        return self.status == AccountStatus.COOLDOWN and self.cooldown_until > now

    def to_public(self, *, masked_session: str = "", masked_cookies: str = "") -> dict[str, Any]:
        """导出为对外（脱敏）字典。"""
        data = asdict(self)
        data.pop("session_key_enc", None)
        data.pop("cookies_enc", None)
        data["status"] = self.status.value
        data["masked_session"] = masked_session
        data["masked_cookies"] = masked_cookies
        data["has_session"] = bool(self.session_key_enc)
        data["has_cookies"] = bool(self.cookies_enc)
        return data
