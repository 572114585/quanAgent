from __future__ import annotations

from types import SimpleNamespace

from tools import mineru_utils


def test_mineru_adapter_invokes_only_workspace_skill_and_caches(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    script = workspace / "skills" / "mineru" / "scripts" / "extract.py"
    script.parent.mkdir(parents=True)
    script.write_text("# skill fixture", encoding="utf-8")
    monkeypatch.setattr(mineru_utils, "WORKSPACE_ROOT", workspace)
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        output_arg = command[command.index("-o") + 1]
        output = workspace / output_arg
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("# Parsed\n\n" + ("MinerU evidence text. " * 10), encoding="utf-8")
        assert kwargs["cwd"] == workspace.resolve()
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout="[OK]", stderr="[INFO] mode: extract")

    monkeypatch.setattr(mineru_utils.subprocess, "run", fake_run)
    first = mineru_utils.extract_with_mineru("https://example.com/paper.pdf")
    second = mineru_utils.extract_with_mineru("https://example.com/paper.pdf")

    assert first.ok is True
    assert first.mode == "extract"
    assert first.output_path.startswith("output/mineru-cache/")
    assert second.mode == "cache"
    assert len(calls) == 1
    assert calls[0][1] == "skills/mineru/scripts/extract.py"
    assert not any("pypdf" in part.casefold() for part in calls[0])


def test_mineru_adapter_redacts_token_from_failure(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    script = workspace / "skills" / "mineru" / "scripts" / "extract.py"
    script.parent.mkdir(parents=True)
    script.write_text("# skill fixture", encoding="utf-8")
    monkeypatch.setattr(mineru_utils, "WORKSPACE_ROOT", workspace)
    monkeypatch.setattr(
        mineru_utils.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="failed --token super-secret-value"
        ),
    )

    result = mineru_utils.extract_with_mineru("https://example.com/bad.pdf")
    assert result.ok is False
    assert "super-secret-value" not in result.error
    assert "[REDACTED]" in result.error
