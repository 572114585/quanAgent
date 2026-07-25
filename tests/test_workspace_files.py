"""无需 Shell 的工作区文件工具测试。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sandbox.backend import _SkillsShellBackend
from tools.workspace_files import inspect_file, replace_file


@pytest.fixture
def file_backend(tmp_path: Path) -> _SkillsShellBackend:
    for subdir in ("tmp", "output", "skills"):
        (tmp_path / subdir).mkdir()
    return _SkillsShellBackend(root_dir=tmp_path, virtual_mode=True)


def test_replace_file_creates_and_atomically_overwrites(
    file_backend: _SkillsShellBackend,
    tmp_path: Path,
):
    first = file_backend.replace_file("/tmp/report.md", "旧内容")
    assert first.error is None
    assert (tmp_path / "tmp" / "report.md").read_bytes() == "旧内容".encode()

    second = file_backend.replace_file("/tmp/report.md", "新内容\n第二行")
    assert second.error is None
    assert (tmp_path / "tmp" / "report.md").read_text(encoding="utf-8") == "新内容\n第二行"
    assert not list((tmp_path / "tmp").glob(".report.md.*.tmp"))


def test_inspect_file_reports_metadata_tail_and_literal_counts(
    file_backend: _SkillsShellBackend,
    tmp_path: Path,
):
    text = "alpha\nbeta esmchina\n抓取记录 esmchina\nlast"
    target = tmp_path / "tmp" / "research.md"
    target.write_text(text, encoding="utf-8", newline="")

    result = file_backend.inspect_file(
        "/tmp/research.md",
        tail_lines=2,
        count_literals=["esmchina", "抓取记录"],
    )

    assert result["ok"] is True
    assert result["size_bytes"] == len(text.encode("utf-8"))
    assert result["line_count"] == 4
    assert result["char_count"] == len(text)
    assert result["tail"] == "抓取记录 esmchina\nlast"
    assert result["literal_counts"] == {"esmchina": 2, "抓取记录": 1}


def test_inspect_file_rejects_oversized_scan(
    file_backend: _SkillsShellBackend,
    tmp_path: Path,
):
    target = tmp_path / "tmp" / "large.txt"
    with target.open("wb") as handle:
        handle.seek(20 * 1024 * 1024)
        handle.write(b"x")

    result = file_backend.inspect_file("/tmp/large.txt")
    assert result["ok"] is False
    assert result["size_bytes"] == 20 * 1024 * 1024 + 1
    assert "扫描上限" in result["error"]


def test_file_helpers_reject_traversal_and_protected_writes(
    file_backend: _SkillsShellBackend,
):
    inspected = file_backend.inspect_file("../outside.txt")
    assert inspected["ok"] is False
    assert "Path traversal" in inspected["error"]

    replaced = file_backend.replace_file("/skills/unsafe.py", "print('no')")
    assert replaced.error is not None
    assert "skills" in replaced.error


def test_file_helpers_reject_symlink_escape(
    file_backend: _SkillsShellBackend,
    tmp_path: Path,
):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "tmp" / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不允许创建测试用目录符号链接")

    inspected = file_backend.inspect_file("/tmp/escape/secret.txt")
    replaced = file_backend.replace_file("/tmp/escape/secret.txt", "no")
    assert inspected["ok"] is False
    assert "outside root" in inspected["error"]
    assert replaced.error is not None
    assert "outside root" in replaced.error


def test_langchain_tools_use_backend_without_shell(
    file_backend: _SkillsShellBackend,
    monkeypatch: pytest.MonkeyPatch,
):
    import sandbox

    monkeypatch.setattr(sandbox, "backend", file_backend)

    write_payload = json.loads(
        replace_file.invoke({"file_path": "/output/result.md", "content": "a\nb"})
    )
    inspect_payload = json.loads(
        inspect_file.invoke({"file_path": "/output/result.md", "tail_lines": 1})
    )

    assert write_payload["ok"] is True
    assert inspect_payload["ok"] is True
    assert inspect_payload["tail"] == "b"


def test_compiled_agent_registers_safe_file_tools():
    from agent_core.runtime import agent

    tools_by_name = agent.nodes["tools"].bound.tools_by_name
    assert {
        "read_file",
        "write_file",
        "inspect_file",
        "replace_file",
        "check_research_material",
    }.issubset(tools_by_name)
