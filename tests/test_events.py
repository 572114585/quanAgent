"""流式事件契约单测。"""
import json

from agent_core.events import SCHEMA_VERSION, V1_EVENT_TYPES, make_event
from agent_core.stream_emit import emit_ndjson


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


def test_schema_version_is_3():
    assert SCHEMA_VERSION == 3
    evt = make_event("start", messageId="m", run_id="r", seq=3)
    assert evt["runId"] == "r"
    assert evt["eventId"] == "r:3"


def test_emit_ndjson_writes_utf8_to_binary_backed_stream():
    class BinarySink:
        def __init__(self):
            self.payload = b""

        def write(self, value):
            self.payload += value

        def flush(self):
            pass

    class LegacyTextStream:
        encoding = "gbk"

        def __init__(self):
            self.buffer = BinarySink()

        def write(self, _value):  # pragma: no cover - UTF-8 path must use buffer
            raise AssertionError("legacy text encoder should not receive NDJSON")

        def flush(self):
            pass

    output = LegacyTextStream()
    emit_ndjson(make_event("delta", delta="non‑breaking hyphen"), file=output)
    assert json.loads(output.buffer.payload.decode("utf-8"))["delta"] == "non‑breaking hyphen"
