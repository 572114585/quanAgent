"""共享流式事件构造（Web / CLI 共用 schema）。

完整 LangGraph → 事件 的转换仍在 entrypoints/web._stream_agent；
本模块提供 make_event 再导出与 CLI NDJSON 辅助。
"""
from __future__ import annotations

import json
from typing import Any, TextIO

from agent_core.events import SCHEMA_VERSION, V1_EVENT_TYPES, V3_EVENT_TYPES, make_event

__all__ = ["SCHEMA_VERSION", "V1_EVENT_TYPES", "V3_EVENT_TYPES", "make_event", "emit_ndjson"]


def emit_ndjson(event: dict[str, Any], file: TextIO | None = None) -> None:
    """将事件写成一行 NDJSON（CLI --format streaming-json）。"""
    import sys

    out = file or sys.stdout
    # JSON event streams are UTF-8 by contract.  On Windows, stdout redirected
    # to a file can otherwise retain a GBK encoder and fail on valid model text
    # such as a non-breaking hyphen.
    line = json.dumps(event, ensure_ascii=False) + "\n"
    buffer = getattr(out, "buffer", None)
    if buffer is not None:
        buffer.write(line.encode("utf-8"))
        buffer.flush()
        return
    out.write(line)
    out.flush()
