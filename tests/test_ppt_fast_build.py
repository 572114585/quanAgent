"""Fast PPT lane: compact contract, concurrent workers, and safe fallbacks."""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

import pytest

import tools.ppt_fast_build as fast


def _contract(slides: int = 8) -> dict:
    return {
        "schema": fast.CONTRACT_SCHEMA,
        "canvas": fast.CANVAS,
        "palette": {"background": "#fff", "ink": "#111", "accent": "#06f", "muted": "#666"},
        "fonts": {"heading": "Aptos", "body": "Aptos"},
        "output_name": "fast-test.pptx",
        "sources": [],
        "prototype": "presentation_core",
        "slides": [
            {
                "number": index + 1,
                "role": "content",
                "core_message": f"Slide {index + 1}",
                "layout_key": "content",
                "content_blocks": [{"type": "bullets", "items": ["A", "B"]}],
            }
            for index in range(slides)
        ],
        "image_tasks": [],
    }


@pytest.fixture
def project_path() -> Path:
    project = Path("workspace/tmp") / f"pytest-fast-{uuid.uuid4().hex[:8]}"
    project.mkdir(parents=True)
    try:
        yield project
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_contract_rejects_caps_and_path_escape(project_path: Path) -> None:
    contract = _contract(13)
    with pytest.raises(ValueError, match="1 to 12"):
        fast.validate_fast_contract(contract, project_path)
    contract = _contract(1)
    contract["sources"] = ["../../outside.md"]
    with pytest.raises(ValueError, match="escapes"):
        fast.validate_fast_contract(contract, project_path)
    contract = _contract(1)
    contract["image_tasks"] = [{}, {}, {}, {}]
    with pytest.raises(ValueError, match="at most"):
        fast.validate_fast_contract(contract, project_path)


def test_four_workers_are_concurrent_and_write_only_assigned_pages(project_path: Path, monkeypatch) -> None:
    (project_path / "fast_contract.json").write_text(json.dumps(_contract()), encoding="utf-8")
    active = 0
    peak = 0
    assignments: list[set[int]] = []

    async def worker(slides, contract):
        nonlocal active, peak
        assignments.append({slide["number"] for slide in slides})
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return {slide["number"]: fast._fallback_svg(slide, contract) for slide in slides}

    monkeypatch.setattr(fast, "_run_quick_checker", lambda project: (True, ""))
    monkeypatch.setattr(fast, "_export_pptx", lambda project, name: None)
    monkeypatch.setattr(fast, "_render_contact_sheets", lambda project, pages: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(fast, "_review_contact_sheets", lambda sheets: asyncio.sleep(0, result="reviewed once"))
    result = asyncio.run(fast.ppt_fast_build(str(project_path), model_worker=worker))

    assert result.workers == 4
    assert peak == 4
    assert set().union(*assignments) == set(range(1, 9))
    assert sum(map(len, assignments)) == 8
    assert result.fallback_pages == []
    assert sorted(path.name for path in (project_path / "svg_output").glob("*.svg")) == result.pages
    assert json.loads((project_path / "validation/fast_run.json").read_text(encoding="utf-8"))["workers"] == 4


def test_invalid_worker_svg_downgrades_without_blocking_other_workers(project_path: Path, monkeypatch) -> None:
    (project_path / "fast_contract.json").write_text(json.dumps(_contract(4)), encoding="utf-8")

    async def worker(slides, contract):
        if slides[0]["number"] == 1:
            return {slide["number"]: "not svg" for slide in slides}
        return {slide["number"]: fast._fallback_svg(slide, contract) for slide in slides}

    monkeypatch.setattr(fast, "_run_quick_checker", lambda project: (True, ""))
    monkeypatch.setattr(fast, "_export_pptx", lambda project, name: None)
    monkeypatch.setattr(fast, "_render_contact_sheets", lambda project, pages: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(fast, "_review_contact_sheets", lambda sheets: asyncio.sleep(0, result="reviewed once"))
    result = asyncio.run(fast.ppt_fast_build(str(project_path), model_worker=worker))

    assert result.pages == ["slide_01.svg", "slide_02.svg", "slide_03.svg", "slide_04.svg"]
    assert result.fallback_pages == ["slide_01.svg"]
    assert all("viewBox=\"0 0 1600 900\"" in path.read_text(encoding="utf-8") for path in (project_path / "svg_output").glob("*.svg"))


def test_worker_timeout_uses_editable_fallbacks(project_path: Path, monkeypatch) -> None:
    (project_path / "fast_contract.json").write_text(json.dumps(_contract(4)), encoding="utf-8")

    async def slow_worker(slides, contract):
        await asyncio.sleep(0.05)
        return {}

    monkeypatch.setattr(fast, "PPT_PAGE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(fast, "_run_quick_checker", lambda project: (True, ""))
    monkeypatch.setattr(fast, "_export_pptx", lambda project, name: None)
    monkeypatch.setattr(fast, "_render_contact_sheets", lambda project, pages: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(fast, "_review_contact_sheets", lambda sheets: asyncio.sleep(0, result="reviewed once"))
    result = asyncio.run(fast.ppt_fast_build(str(project_path), model_worker=slow_worker))

    assert result.fallback_pages == result.pages
    assert result.phase_seconds["parallel_pages_and_images"] < 0.04
