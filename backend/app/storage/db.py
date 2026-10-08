"""
db.py - SQLite 存储。

集中管理连接与表结构，提供调用日志、会话、消息、反馈、模型画像、路由日志的读 written 方法。
使用 WAL 模式与线程锁，保证 FastAPI 多线程下的安全访问。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS call_logs (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    requested_model TEXT,
    resolved_model TEXT,
    platform TEXT,
    variant TEXT,
    account_id TEXT,
    stream INTEGER DEFAULT 0,
    status TEXT,
    latency_ms INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    error TEXT,
    route_reason TEXT,
    auto INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_call_logs_ts ON call_logs(ts);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    model TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    call_log_id TEXT,
    rating TEXT,
    comment TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS model_profiles (
    platform TEXT NOT NULL,
    variant TEXT NOT NULL,
    model TEXT,
    task_type TEXT NOT NULL DEFAULT 'general',
    accuracy REAL DEFAULT 0.7,
    avg_latency_ms REAL DEFAULT 0,
    cost REAL DEFAULT 0.7,
    samples INTEGER DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (platform, variant, task_type)
);

CREATE TABLE IF NOT EXISTS route_logs (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    requested_model TEXT,
    resolved_model TEXT,
    platform TEXT,
    variant TEXT,
    reason TEXT,
    score REAL,
    candidates TEXT
);
CREATE INDEX IF NOT EXISTS idx_route_logs_ts ON route_logs(ts);
"""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_settings().db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        logger.info("SQLite 已就绪: %s", self._path)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    # ---- 调用日志 ----
    def log_call(self, **fields: Any) -> str:
        log_id = fields.get("id") or uuid.uuid4().hex[:16]
        self._execute(
            """INSERT INTO call_logs
               (id, ts, requested_model, resolved_model, platform, variant, account_id,
                stream, status, latency_ms, prompt_tokens, completion_tokens, total_tokens,
                error, route_reason, auto)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                log_id,
                fields.get("ts", time.time()),
                fields.get("requested_model", ""),
                fields.get("resolved_model", ""),
                fields.get("platform", ""),
                fields.get("variant", ""),
                fields.get("account_id", ""),
                1 if fields.get("stream") else 0,
                fields.get("status", "ok"),
                int(fields.get("latency_ms", 0)),
                int(fields.get("prompt_tokens", 0)),
                int(fields.get("completion_tokens", 0)),
                int(fields.get("total_tokens", 0)),
                fields.get("error", ""),
                fields.get("route_reason", ""),
                1 if fields.get("auto") else 0,
            ),
        )
        return log_id

    def list_calls(self, *, limit: int = 100, offset: int = 0, status: str = "", platform: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM call_logs WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in self._query(sql, tuple(params))]

    def stats_summary(self) -> dict[str, Any]:
        day_start = time.time() - 86400
        row = self._query_one(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok,
                      AVG(latency_ms) AS avg_latency,
                      SUM(total_tokens) AS tokens
               FROM call_logs WHERE ts >= ?""",
            (day_start,),
        )
        total = (row["total"] or 0) if row else 0
        ok = (row["ok"] or 0) if row else 0
        return {
            "window": "24h",
            "total": total,
            "success": ok,
            "success_rate": round(ok / total, 4) if total else 0.0,
            "avg_latency_ms": round(row["avg_latency"] or 0, 1) if row else 0.0,
            "total_tokens": int(row["tokens"] or 0) if row else 0,
        }

    def stats_series(self, *, hours: int = 24) -> list[dict[str, Any]]:
        """按小时聚合的调用量与成功率。"""
        start = time.time() - hours * 3600
        rows = self._query(
            "SELECT ts, status, latency_ms, total_tokens FROM call_logs WHERE ts >= ? ORDER BY ts ASC",
            (start,),
        )
        buckets: dict[int, dict[str, Any]] = {}
        for row in rows:
            bucket_ts = int(row["ts"] // 3600) * 3600
            b = buckets.setdefault(bucket_ts, {"ts": bucket_ts, "count": 0, "ok": 0, "latency": 0.0, "tokens": 0})
            b["count"] += 1
            if row["status"] == "ok":
                b["ok"] += 1
            b["latency"] += row["latency_ms"] or 0
            b["tokens"] += row["total_tokens"] or 0
        series = []
        for b in sorted(buckets.values(), key=lambda x: x["ts"]):
            count = b["count"] or 1
            series.append(
                {
                    "ts": b["ts"],
                    "count": b["count"],
                    "success_rate": round(b["ok"] / count, 4),
                    "avg_latency_ms": round(b["latency"] / count, 1),
                    "tokens": b["tokens"],
                }
            )
        return series

    # ---- 会话 ----
    def create_conversation(self, title: str, model: str) -> str:
        conv_id = uuid.uuid4().hex[:16]
        now = time.time()
        self._execute(
            "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?,?,?,?,?)",
            (conv_id, title or "新对话", model, now, now),
        )
        return conv_id

    def list_conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self._query(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
        ]

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        if row is None:
            return None
        data = dict(row)
        data["messages"] = [
            dict(m)
            for m in self._query(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conv_id,),
            )
        ]
        return data

    def add_message(self, conv_id: str, role: str, content: str) -> None:
        now = time.time()
        self._execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
            (uuid.uuid4().hex[:16], conv_id, role, content, now),
        )
        self._execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))

    def rename_conversation(self, conv_id: str, title: str) -> None:
        self._execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))

    def delete_conversation(self, conv_id: str) -> None:
        self._execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        self._execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

    # ---- 反馈 ----
    def add_feedback(self, call_log_id: str, rating: str, comment: str = "") -> str:
        fb_id = uuid.uuid4().hex[:16]
        self._execute(
            "INSERT INTO feedback (id, call_log_id, rating, comment, created_at) VALUES (?,?,?,?,?)",
            (fb_id, call_log_id, rating, comment, time.time()),
        )
        return fb_id

    # ---- 模型画像 ----
    def upsert_profile(
        self,
        platform: str,
        variant: str,
        *,
        model: str = "",
        task_type: str = "general",
        accuracy: float | None = None,
        avg_latency_ms: float | None = None,
        cost: float | None = None,
        samples: int | None = None,
    ) -> None:
        existing = self._query_one(
            "SELECT * FROM model_profiles WHERE platform=? AND variant=? AND task_type=?",
            (platform, variant, task_type),
        )
        now = time.time()
        if existing is None:
            self._execute(
                """INSERT INTO model_profiles
                   (platform, variant, model, task_type, accuracy, avg_latency_ms, cost, samples, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    platform,
                    variant,
                    model,
                    task_type,
                    accuracy if accuracy is not None else 0.7,
                    avg_latency_ms if avg_latency_ms is not None else 0.0,
                    cost if cost is not None else 0.7,
                    samples or 0,
                    now,
                ),
            )
            return
        self._execute(
            """UPDATE model_profiles SET
                 accuracy = COALESCE(?, accuracy),
                 avg_latency_ms = COALESCE(?, avg_latency_ms),
                 cost = COALESCE(?, cost),
                 samples = COALESCE(?, samples),
                 model = CASE WHEN ? != '' THEN ? ELSE model END,
                 updated_at = ?
               WHERE platform=? AND variant=? AND task_type=?""",
            (
                accuracy,
                avg_latency_ms,
                cost,
                samples,
                model,
                model,
                now,
                platform,
                variant,
                task_type,
            ),
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query("SELECT * FROM model_profiles ORDER BY platform, variant")]

    def get_profile(self, platform: str, variant: str, task_type: str = "general") -> dict[str, Any] | None:
        row = self._query_one(
            "SELECT * FROM model_profiles WHERE platform=? AND variant=? AND task_type=?",
            (platform, variant, task_type),
        )
        return dict(row) if row else None

    # ---- 路由日志 ----
    def log_route(self, **fields: Any) -> str:
        log_id = uuid.uuid4().hex[:16]
        candidates = fields.get("candidates") or []
        self._execute(
            """INSERT INTO route_logs
               (id, ts, requested_model, resolved_model, platform, variant, reason, score, candidates)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                log_id,
                fields.get("ts", time.time()),
                fields.get("requested_model", ""),
                fields.get("resolved_model", ""),
                fields.get("platform", ""),
                fields.get("variant", ""),
                fields.get("reason", ""),
                float(fields.get("score") or 0.0),
                json.dumps(candidates, ensure_ascii=False),
            ),
        )
        return log_id

    def list_routes(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM route_logs ORDER BY ts DESC LIMIT ?", (limit,))
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["candidates"] = json.loads(item.get("candidates") or "[]")
            except json.JSONDecodeError:
                item["candidates"] = []
            result.append(item)
        return result


_db: Database | None = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
