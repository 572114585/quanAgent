"""Append-only 事件日志：支撑 SSE 断线补流与 eventId 游标。

落在 workspace/state/events.sqlite（与 checkpoints 同目录、独立文件），
避免与 LangGraph checkpointer 表结构耦合。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from agent_core.config import EVENT_LOG_DB_PATH, STATE_DIR, ensure_runtime_dirs
from agent_core.events import make_event_id

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS agent_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_events_thread_id
    ON agent_events(thread_id, id);
CREATE INDEX IF NOT EXISTS idx_agent_events_run_seq
    ON agent_events(run_id, seq);
"""


class EventLog:
    """线程安全的 append-only 事件存储。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(_CREATE_SQL)
        conn.commit()

    def append(
        self,
        *,
        thread_id: str,
        run_id: str,
        seq: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> str:
        """写入一条事件，返回 event_id。payload 应已含 type/runId/eventId。"""
        event_id = str(payload.get("eventId") or make_event_id(run_id, seq))
        body = dict(payload)
        body.setdefault("runId", run_id)
        body.setdefault("eventId", event_id)
        body.setdefault("type", event_type)
        with self._lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO agent_events "
                "(thread_id, run_id, seq, event_id, type, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    run_id,
                    seq,
                    event_id,
                    event_type,
                    json.dumps(body, ensure_ascii=False),
                    time.time(),
                ),
            )
            self.conn.commit()
        return event_id

    def replay(
        self,
        thread_id: str,
        *,
        after_event_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """按 thread 重放事件；after_event_id 之后（不含）的下一批。"""
        limit = max(1, min(int(limit), 2000))
        with self._lock:
            if after_event_id:
                row = self.conn.execute(
                    "SELECT id FROM agent_events WHERE event_id = ? AND thread_id = ?",
                    (after_event_id, thread_id),
                ).fetchone()
                after_row_id = int(row[0]) if row else 0
                cur = self.conn.execute(
                    "SELECT payload_json FROM agent_events "
                    "WHERE thread_id = ? AND id > ? "
                    "ORDER BY id ASC LIMIT ?",
                    (thread_id, after_row_id, limit),
                )
            else:
                cur = self.conn.execute(
                    "SELECT payload_json FROM agent_events "
                    "WHERE thread_id = ? ORDER BY id ASC LIMIT ?",
                    (thread_id, limit),
                )
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for (payload_json,) in rows:
            try:
                out.append(json.loads(payload_json))
            except json.JSONDecodeError:
                continue
        return out

    def latest_event_id(self, thread_id: str) -> str | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT event_id FROM agent_events "
                "WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
        return str(row[0]) if row else None


_event_log: EventLog | None = None


def get_event_log() -> EventLog:
    """惰性创建模块级 EventLog 单例。"""
    global _event_log
    if _event_log is None:
        ensure_runtime_dirs()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(EVENT_LOG_DB_PATH), check_same_thread=False)
        _event_log = EventLog(conn)
    return _event_log


def reset_event_log_for_tests() -> None:
    """测试用：关闭并清空单例（下次 get_event_log 重建）。"""
    global _event_log
    if _event_log is not None:
        try:
            _event_log.conn.close()
        except Exception:  # noqa: BLE001
            pass
        _event_log = None
