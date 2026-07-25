"""Per-thread 运行注册表：会话串行锁、活跃 run、取消信号。"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class RunConflictError(Exception):
    """同 thread 已有活跃 run。"""

    def __init__(self, thread_id: str, active_run_id: str):
        self.thread_id = thread_id
        self.active_run_id = active_run_id
        super().__init__(
            f"thread {thread_id!r} already has active run {active_run_id!r}"
        )


@dataclass
class ActiveRun:
    run_id: str
    thread_id: str
    started_at: float
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    deadline_at: float | None = None

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def is_past_deadline(self) -> bool:
        return self.deadline_at is not None and time.time() >= self.deadline_at


class RunRegistry:
    """进程内 per-thread 运行互斥与取消。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[str, ActiveRun] = {}
        self._thread_locks: dict[str, asyncio.Lock] = {}

    def _thread_lock(self, thread_id: str) -> asyncio.Lock:
        lock = self._thread_locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self._thread_locks[thread_id] = lock
        return lock

    async def try_begin(
        self,
        thread_id: str,
        *,
        run_id: str | None = None,
        deadline_seconds: float | None = None,
    ) -> ActiveRun:
        """尝试启动新 run；若已有活跃 run 则抛 RunConflictError。"""
        async with self._lock:
            existing = self._active.get(thread_id)
            if existing is not None and not existing.cancelled:
                raise RunConflictError(thread_id, existing.run_id)
            rid = run_id or str(uuid.uuid4())
            deadline_at = (
                time.time() + float(deadline_seconds)
                if deadline_seconds and deadline_seconds > 0
                else None
            )
            active = ActiveRun(
                run_id=rid,
                thread_id=thread_id,
                started_at=time.time(),
                deadline_at=deadline_at,
            )
            self._active[thread_id] = active
            return active

    async def end(self, thread_id: str, run_id: str | None = None) -> None:
        async with self._lock:
            current = self._active.get(thread_id)
            if current is None:
                return
            if run_id and current.run_id != run_id:
                return
            self._active.pop(thread_id, None)

    def get(self, thread_id: str) -> ActiveRun | None:
        return self._active.get(thread_id)

    def active_run_id(self, thread_id: str) -> str | None:
        run = self._active.get(thread_id)
        return run.run_id if run else None

    async def cancel(self, thread_id: str, run_id: str | None = None) -> bool:
        """取消活跃 run；返回是否找到并取消。"""
        async with self._lock:
            current = self._active.get(thread_id)
            if current is None:
                return False
            if run_id and current.run_id != run_id:
                return False
            current.cancel_event.set()
            task = current.task
        if task is not None and not task.done():
            task.cancel()
        return True

    def attach_task(self, thread_id: str, task: asyncio.Task) -> None:
        run = self._active.get(thread_id)
        if run is not None:
            run.task = task

    def should_stop(self, thread_id: str) -> bool:
        run = self._active.get(thread_id)
        if run is None:
            return False
        return run.cancelled or run.is_past_deadline()


_registry: RunRegistry | None = None


def get_run_registry() -> RunRegistry:
    global _registry
    if _registry is None:
        _registry = RunRegistry()
    return _registry


def reset_run_registry_for_tests() -> None:
    global _registry
    _registry = None
