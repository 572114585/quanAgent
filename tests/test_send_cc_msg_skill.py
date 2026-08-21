"""Tests for the file-based CC notification Skill."""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from agent_core.execute_policy import classify_execute_command
from agent_core.permissions import build_interrupt_on, resolve_permission
from sandbox.path_rewriter import _discover_skill_scripts


SKILL_ROOT = Path("workspace/skills/send-cc-msg")
SCRIPT = SKILL_ROOT / "scripts/send_cc_msg.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("send_cc_msg_skill_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_files_and_frontmatter_are_discoverable() -> None:
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "references/config.md").is_file()
    assert SCRIPT.is_file()

    frontmatter = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    assert "name: send_cc_msg" in frontmatter
    assert "allowed-tools: execute" in frontmatter
    assert "skills/send-cc-msg/scripts/send_cc_msg.py" in _discover_skill_scripts(Path("workspace"))


@pytest.mark.parametrize(
    "command",
    [
        "python skills/send-cc-msg/scripts/send_cc_msg.py --receiver_id 1 --message hi",
        "python.exe skills\\send-cc-msg\\scripts\\send_cc_msg.py --receiver_id 1 --message hi",
        "python D:\\codes\\quanAgent\\workspace\\skills\\send-cc-msg\\scripts\\send_cc_msg.py --receiver_id 1 --message hi",
    ],
)
def test_cc_notification_is_non_delete_command(command: str) -> None:
    classification = classify_execute_command(command)
    assert classification.effect == "auto"
    assert classification.reason == "allowed_command"


def test_regular_skill_script_stays_auto() -> None:
    classification = classify_execute_command("python skills/word-docx/scripts/create.py")
    assert classification.effect == "auto"
    assert classification.reason == "allowed_command"


def test_cc_notification_in_command_chain_is_allowed() -> None:
    classification = classify_execute_command(
        "echo preparing && python skills/send-cc-msg/scripts/send_cc_msg.py --receiver_id 1 --message hi"
    )
    assert classification.effect == "auto"
    assert classification.reason == "allowed_command"


def test_cc_notification_uses_default_execute_permission() -> None:
    command = "python skills/send-cc-msg/scripts/send_cc_msg.py --receiver_id 1 --message hi"

    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": command},
        )
        == "allow"
    )

    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is None


def test_inline_python_is_not_misclassified_as_cc_script() -> None:
    classification = classify_execute_command(
        'python -c "print(\'skills/send-cc-msg/scripts/send_cc_msg.py\')"'
    )
    assert classification.effect == "auto"
    assert classification.reason == "allowed_command"


def test_build_cc_message_supports_defaults_and_single_thumbnail() -> None:
    module = _load_script()
    message = module.build_cc_message(
        "正文",
        thumbnail_url="https://example.com/a.jpg",
        thumbnail_text="查看详情",
    )
    assert "[banner_img_B]" in message
    assert "[title_B]大人，您有新的通知/进展~[title_E]" in message
    assert "[version_B]2[version_E]正文" in message
    assert "[url_B]https://example.com/a.jpg[url_E]" in message
    assert "[url_show_B]查看详情[url_show_E]" in message


def test_build_cc_message_prefers_multiple_thumbnails() -> None:
    module = _load_script()
    message = module.build_cc_message(
        "正文",
        thumbnail_url="https://example.com/fallback.jpg",
        thumbnail_urls=" https://example.com/a.jpg,https://example.com/b.jpg ",
    )
    assert "https://example.com/a.jpg" in message
    assert "https://example.com/b.jpg" in message
    assert "fallback.jpg" not in message


def test_send_cc_message_double_encodes_and_retries_receiver_types(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script()
    calls: list[tuple[str, dict]] = []

    class Response:
        def __init__(self, *, json_data: dict | None = None, text: str = "") -> None:
            self._json_data = json_data or {}
            self.text = text

        def json(self) -> dict:
            return self._json_data

    responses = iter(
        [
            Response(json_data={"error_code": 0, "token": "token-1"}),
            Response(text='{"error_code": 1001}'),
            Response(text='{"error_code": 0}'),
        ]
    )

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs["json"]))
        return next(responses)

    monkeypatch.setattr(module.requests, "post", fake_post)
    result = module.send_cc_message(
        receiver_id="001,002，003",
        message="消息正文",
        login_url="https://cc.example/login",
        send_url="https://cc.example/send",
        username="sender",
        password="secret",
    )

    assert result["success"] is True
    assert result["receiveridtype"] == 2
    assert len(calls) == 3
    assert calls[0][0].endswith("login")
    assert calls[1][1]["receiverids"] == ["001", "002", "003"]
    encoded = calls[1][1]["msgdata"]
    decoded_once = base64.b64decode(encoded).decode("utf-8")
    decoded_twice = base64.b64decode(decoded_once).decode("utf-8")
    assert "消息正文" in decoded_twice


@pytest.mark.parametrize(
    "receiver_id,message",
    [("", "正文"), ("001", "")],
)
def test_send_cc_message_validates_required_inputs(receiver_id: str, message: str) -> None:
    module = _load_script()
    result = module.send_cc_message(
        receiver_id=receiver_id,
        message=message,
        login_url="https://cc.example/login",
        send_url="https://cc.example/send",
        username="sender",
        password="secret",
    )
    assert result["success"] is False
