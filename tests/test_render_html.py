"""Regression tests for HTML-to-PNG path handling."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from tools.render_html import _resolve_html_path


def test_resolve_html_path_uses_the_configured_workspace_root() -> None:
    test_tmp = Path(__file__).resolve().parents[1] / "workspace" / "tmp"
    with TemporaryDirectory(dir=test_tmp) as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        html = workspace / "output" / "chart.html"
        html.parent.mkdir(parents=True)
        html.write_text("<!doctype html><html></html>", encoding="utf-8")

        assert _resolve_html_path("output/chart.html", workspace) == html.resolve()


def test_resolve_html_path_rejects_paths_outside_workspace() -> None:
    test_tmp = Path(__file__).resolve().parents[1] / "workspace" / "tmp"
    with TemporaryDirectory(dir=test_tmp) as temp_dir:
        temp_root = Path(temp_dir)
        workspace = temp_root / "workspace"
        workspace.mkdir()
        outside = temp_root / "outside.html"
        outside.write_text("<!doctype html><html></html>", encoding="utf-8")

        assert _resolve_html_path(str(outside), workspace) is None
