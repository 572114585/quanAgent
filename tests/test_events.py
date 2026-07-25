"""流式事件契约单测。"""
from agent_core.events import SCHEMA_VERSION, V1_EVENT_TYPES, make_event


def test_make_event_start_includes_schema_version():
    evt = make_event("start", messageId="m1")
    assert evt["type"] == "start"
    assert evt["messageId"] == "m1"
    assert evt["schemaVersion"] == SCHEMA_VERSION


def test_make_event_delta_omits_version_by_default():
    evt = make_event("delta", delta="hi")
    assert evt == {"type": "delta", "delta": "hi"}
    assert "schemaVersion" not in evt


def test_make_event_can_force_version():
    evt = make_event("delta", include_version=True, delta="hi")
    assert evt["schemaVersion"] == SCHEMA_VERSION


def test_v1_frozen_set():
    assert "start" in V1_EVENT_TYPES
    assert "tool_call" in V1_EVENT_TYPES
    assert "usage" not in V1_EVENT_TYPES  # deferred


def test_schema_version_is_2():
    assert SCHEMA_VERSION == 2
    evt = make_event("start", messageId="m", run_id="r", seq=3)
    assert evt["runId"] == "r"
    assert evt["eventId"] == "r:3"