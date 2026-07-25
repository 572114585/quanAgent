"""EventLog append / replay 单测。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import agent_core.event_log as event_log_mod
from agent_core.event_log import EventLog, reset_event_log_for_tests
from agent_core.events import SCHEMA_VERSION, make_event, make_event_id


def test_make_event_v2_includes_run_and_event_id():
    evt = make_event("start", messageId="m1", run_id="r1", seq=1)
    assert evt["schemaVersion"] == SCHEMA_VERSION
    assert evt["runId"] == "r1"
    assert evt["eventId"] == make_event_id("r1", 1)
    assert SCHEMA_VERSION == 2


def test_event_log_append_and_replay(tmp_path: Path, monkeypatch):
    reset_event_log_for_tests()
    db = tmp_path / "events.sqlite"
    monkeypatch.setattr(event_log_mod, "EVENT_LOG_DB_PATH", db)
    # 绕过 get_event_log 单例，直接构造
    import sqlite3

    log = EventLog(sqlite3.connect(str(db), check_same_thread=False))
    p1 = make_event("start", messageId="m", run_id="runA", seq=1)
    p2 = make_event("delta", delta="hi", run_id="runA", seq=2)
    log.append(thread_id="t1", run_id="runA", seq=1, event_type="start", payload=p1)
    log.append(thread_id="t1", run_id="runA", seq=2, event_type="delta", payload=p2)

    all_ev = log.replay("t1")
    assert len(all_ev) == 2
    assert all_ev[0]["type"] == "start"
    assert all_ev[1]["delta"] == "hi"

    after = log.replay("t1", after_event_id=p1["eventId"])
    assert len(after) == 1
    assert after[0]["eventId"] == p2["eventId"]
    assert log.latest_event_id("t1") == p2["eventId"]
    reset_event_log_for_tests()
