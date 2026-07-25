"""execute 信任级别：HITL 批准后可绕过沙盒软白名单。

deepagents LocalShellBackend.execute(command) 无法改签名，用 ContextVar
在 HooksMiddleware 包住 handler 期间传递信任级别。

- strict（默认）：软白名单 + 硬拒绝均生效
- hitl_approved：仅硬拒绝生效（命令替换、cd 越界、极危险模式）
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Literal

TrustLevel = Literal["strict", "hitl_approved"]

_execute_trust_level: ContextVar[TrustLevel] = ContextVar(
    "execute_trust_level", default="strict"
)


def get_execute_trust_level() -> TrustLevel:
    return _execute_trust_level.get()


def set_execute_trust_level(level: TrustLevel) -> Token:
    return _execute_trust_level.set(level)


def reset_execute_trust_level(token: Token) -> None:
    _execute_trust_level.reset(token)


@contextmanager
def execute_trust(level: TrustLevel) -> Iterator[None]:
    token = set_execute_trust_level(level)
    try:
        yield
    finally:
        reset_execute_trust_level(token)
