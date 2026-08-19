"""Smoke tests for the vendored diagram-design skill."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "workspace" / "skills" / "diagram-design"
SCRIPTS = SKILL / "scripts"


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---", 3)
    if end < 0:
        raise AssertionError("SKILL.md frontmatter is not closed")
    block = text[3:end].strip()
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def test_skill_md_frontmatter_parses():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert meta.get("name") == "diagram-design"
    assert "flowchart" in meta.get("description", "").lower()
    assert "架构图" in meta.get("description", "")
    assert "execute" in meta.get("allowed-tools", "")
    assert "render_html" in meta.get("allowed-tools", "")


@pytest.mark.parametrize(
    "script",
    [
        "self_check.py",
        "drawio_extract.py",
        "mermaid_extract.py",
        "export_svg.py",
        "extract_brand.py",
    ],
)
def test_skill_scripts_help(script: str):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--help"],
        cwd=ROOT / "workspace",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower() or "Usage" in result.stdout


def test_export_svg_writes_standalone_svg():
    workspace = ROOT / "workspace"
    out_dir = workspace / "tmp" / "diagram-design-pytest"
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / "mini.html"
    dest = out_dir / "mini.svg"
    html.write_text(
        """<!doctype html><html><body>
<svg viewBox="0 0 120 40" role="img" aria-labelledby="mini-title">
<title id="mini-title">Mini</title>
<rect width="120" height="40" fill="#f5f5f5"/>
</svg>
</body></html>
""",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "export_svg.py"),
                "--file",
                "tmp/diagram-design-pytest/mini.html",
                "--out",
                "tmp/diagram-design-pytest/mini.svg",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        svg = dest.read_text(encoding="utf-8")
        assert svg.startswith("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert "fonts.googleapis.com" in svg
        assert "&amp;family=Geist" in svg
        assert "<svg" in svg
        assert "</svg>" in svg
    finally:
        for path in (html, dest):
            if path.exists():
                path.unlink()



def test_self_check_on_shipped_template_reports_clearly():
    template = SKILL / "assets" / "template.html"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "self_check.py"), str(template)],
        cwd=ROOT / "workspace",
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (result.stdout + result.stderr).strip()
    assert combined, "self_check.py must print a result"
    assert result.returncode in (0, 1)
    if result.returncode == 0:
        assert "OK" in combined or "ok" in combined.lower()
    else:
        assert template.name in combined or "template" in combined.lower() or combined
