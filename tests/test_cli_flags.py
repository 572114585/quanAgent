"""CLI 安全相关标志：输出格式不得隐式升权。"""
from __future__ import annotations

from entrypoints.cli import parse_args


def test_streaming_json_with_prompt_does_not_set_always_approve():
    args = parse_args(["-p", "列出 skills", "--format", "streaming-json"])
    assert args.prompt == "列出 skills"
    assert args.format == "streaming-json"
    assert args.always_approve is False


def test_explicit_always_approve_flag():
    args = parse_args(["-p", "hi", "--format", "streaming-json", "--always-approve"])
    assert args.always_approve is True


def test_text_mode_default_no_always_approve():
    args = parse_args(["-p", "hi"])
    assert args.always_approve is False
