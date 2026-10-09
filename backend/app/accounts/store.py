"""
store.py - 账号 JSON 存储。

- 以 data/accounts.json 为持久化载体；
- 支持热重载（依据文件 mtime 自动重读，不重启进程）；
- 去重键为 (platform, email) 与 (platform, session_key 明文)。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logging_config import get_logger
from . import crypto
from .models import Account, AccountStatus

logger = get_logger(__name__)


class AccountStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_settings().accounts_path
        self._lock = threading.RLock()
        self._accounts: dict[str, Account] = {}
        self._mtime: float = 0.0
        self._load()

    # ---- 持久化 ----
    def _serialize(self, account: Account) -> dict[str, Any]:
        data = account.__dict__.copy()
        data["status"] = account.status.value
        return data

    def _deserialize(self, data: dict[str, Any]) -> Account:
        data = dict(data)
        status = data.get("status", AccountStatus.ACTIVE.value)
        data["status"] = AccountStatus(status) if status in {s.value for s in AccountStatus} else AccountStatus.ACTIVE
        allowed = Account.__dataclass_fields__.keys()
        return Account(**{k: v for k, v in data.items() if k in allowed})

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                self._accounts = {}
                self._mtime = 0.0
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("账号文件读取失败，忽略: %s", exc)
                return
            accounts = raw.get("accounts", raw) if isinstance(raw, dict) else raw
            self._accounts = {}
            for item in accounts or []:
                try:
                    account = self._deserialize(item)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("跳过非法账号记录: %s", exc)
                    continue
                self._accounts[account.id] = account
            self._mtime = self._path.stat().st_mtime
            logger.info("已加载 %d 个账号 (platforms=%s)", len(self._accounts), self.platforms())

    def _save(self) -> None:
        payload = {"accounts": [self._serialize(a) for a in self._accounts.values()]}
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        self._mtime = self._path.stat().st_mtime

    def maybe_reload(self) -> None:
        """检测到外部文件变更时热重载。"""
        if not self._path.exists():
            return
        mtime = self._path.stat().st_mtime
        if mtime > self._mtime:
            logger.info("检测到账号文件变更，热重载中…")
            self._load()

    # ---- 查询 ----
    def all(self) -> list[Account]:
        with self._lock:
            self.maybe_reload()
            return list(self._accounts.values())

    def by_platform(self, platform: str) -> list[Account]:
        return [a for a in self.all() if a.platform == platform]

    def get(self, account_id: str) -> Account | None:
        with self._lock:
            self.maybe_reload()
            return self._accounts.get(account_id)

    def platforms(self) -> list[str]:
        return sorted({a.platform for a in self._accounts.values()})

    # ---- 写入 ----
    def _dedup_keys(self, account: Account) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        if account.email:
            keys.add(("email", f"{account.platform}:{account.email.lower()}"))
        session = crypto.decrypt(account.session_key_enc)
        if session:
            keys.add(("session", f"{account.platform}:{session}"))
        return keys

    def _existing_keys(self, exclude_id: str = "") -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for acc in self._accounts.values():
            if acc.id == exclude_id:
                continue
            keys |= self._dedup_keys(acc)
        return keys

    def add(
        self,
        *,
        platform: str,
        email: str = "",
        session_key: str = "",
        cookies: dict[str, Any] | str = "",
        storage: dict[str, Any] | str = "",
        remark: str = "",
    ) -> tuple[Account | None, str]:
        """新增账号，返回 (account, message)。重复则返回 (None, 原因)。"""
        with self._lock:
            self.maybe_reload()
            account = Account(
                platform=platform.strip(),
                email=email.strip(),
                remark=remark.strip(),
                session_key_enc=crypto.encrypt(session_key),
                cookies_enc=crypto.encrypt(
                    cookies if isinstance(cookies, str) else json.dumps(cookies, ensure_ascii=False)
                ),
                storage_enc=crypto.encrypt(
                    storage if isinstance(storage, str) else json.dumps(storage, ensure_ascii=False)
                ),
            )
            dup = self._dedup_keys(account) & self._existing_keys()
            if dup:
                reasons = ", ".join(sorted({d[0] for d in dup}))
                return None, f"账号重复（{reasons}）"
            self._accounts[account.id] = account
            self._save()
            return account, "ok"

    def import_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """批量导入（JSON 数组）。"""
        added, skipped = 0, 0
        errors: list[str] = []
        for item in items:
            account, msg = self.add(
                platform=str(item.get("platform", "")).strip(),
                email=str(item.get("email", "")).strip(),
                session_key=str(item.get("session_key") or item.get("sessionKey") or ""),
                cookies=item.get("cookies") or "",
                storage=item.get("storage") or item.get("local_storage") or "",
                remark=str(item.get("remark", "")),
            )
            if account:
                added += 1
            else:
                skipped += 1
                errors.append(f"{item.get('email') or item.get('platform')}: {msg}")
        return {"added": added, "skipped": skipped, "errors": errors[:20]}

    def update(self, account_id: str, **fields: Any) -> Account | None:
        with self._lock:
            account = self._accounts.get(account_id)
            if account is None:
                return None
            session_key = fields.pop("session_key", None)
            cookies = fields.pop("cookies", None)
            storage = fields.pop("storage", None)
            if session_key is not None:
                account.session_key_enc = crypto.encrypt(str(session_key))
            if cookies is not None:
                account.cookies_enc = crypto.encrypt(
                    cookies if isinstance(cookies, str) else json.dumps(cookies, ensure_ascii=False)
                )
            if storage is not None:
                account.storage_enc = crypto.encrypt(
                    storage if isinstance(storage, str) else json.dumps(storage, ensure_ascii=False)
                )
            for key in ("email", "remark", "platform", "status"):
                if key in fields and fields[key] is not None:
                    value = fields[key]
                    setattr(account, key, AccountStatus(value) if key == "status" else value)
            self._save()
            return account

    def delete(self, account_id: str) -> bool:
        with self._lock:
            if account_id in self._accounts:
                del self._accounts[account_id]
                self._save()
                return True
            return False

    def mark_result(self, account_id: str, *, success: bool, cooldown_seconds: int = 0) -> None:
        with self._lock:
            account = self._accounts.get(account_id)
            if account is None:
                return
            account.call_count += 1
            account.last_used = time.time()
            if success:
                account.success_count += 1
                account.status = AccountStatus.ACTIVE
            else:
                account.fail_count += 1
                if cooldown_seconds > 0:
                    account.status = AccountStatus.COOLDOWN
                    account.cooldown_until = time.time() + cooldown_seconds
            self._save()

    def mark_invalid(self, account_id: str) -> None:
        with self._lock:
            account = self._accounts.get(account_id)
            if account is None:
                return
            account.status = AccountStatus.INVALID
            self._save()
