"""Bounded, checkpoint-free PPT fast-build orchestration.

The normal PPT Master workflows are intentionally deliberative.  This module is
the small, deterministic lane used for ordinary 10--12 page business decks:
one project-local contract, four independent page workers, one final QA pass,
and a safe editable fallback for every failed page.
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from xml.etree import ElementTree as ET

from langchain_core.tools import tool

from agent_core.config import (
    PPT_FAST_DEADLINE_SECONDS,
    PPT_FAST_VISION_TIMEOUT,
    PPT_IMAGE_CONCURRENCY,
    PPT_IMAGE_LIMIT,
    PPT_PAGE_CONCURRENCY,
    PPT_PAGE_TIMEOUT_SECONDS,
    SKILLS_DIR,
    WORKSPACE_ROOT,
)

CONTRACT_SCHEMA = "quanagent.ppt-fast.v1"
CANVAS = {"format": "ppt169", "viewBox": [0, 0, 1600, 900]}
_SVG_NS = "http://www.w3.org/2000/svg"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass
class FastBuildSummary:
    project_path: str
    contract_path: str
    output_path: str | None = None
    elapsed_seconds: float = 0.0
    workers: int = 0
    pages: list[str] = field(default_factory=list)
    image_results: list[dict[str, Any]] = field(default_factory=list)
    review: str = "skipped"
    repaired_pages: list[str] = field(default_factory=list)
    fallback_pages: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    phase_seconds: dict[str, float] = field(default_factory=dict)
    page_concurrency: int = 0
    image_concurrency: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _project_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    allowed = (WORKSPACE_ROOT.resolve(), (WORKSPACE_ROOT / "tmp").resolve())
    if not any(path == root or root in path.parents for root in allowed):
        raise ValueError("project_path must be inside workspace/")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_brief(project: Path) -> str:
    for name in ("README.md", "brief.md", "source_brief.md"):
        candidate = project / name
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")[:8000]
    return project.name.replace("_", " ").replace("-", " ")


def _default_contract(project: Path) -> dict[str, Any]:
    title = _read_brief(project).splitlines()[0].lstrip("# ").strip() or "Business presentation"
    return {
        "schema": CONTRACT_SCHEMA,
        "canvas": CANVAS,
        "palette": {"background": "#F7F8FA", "ink": "#152033", "accent": "#1769E0", "muted": "#64748B"},
        "fonts": {"heading": "Aptos Display", "body": "Aptos"},
        "output_name": f"{project.name}.pptx",
        "sources": [],
        "prototype": "presentation_core",
        "slides": [
            {"number": 1, "role": "title", "core_message": title, "layout_key": "title", "content_blocks": [{"type": "title", "text": title}]},
            {"number": 2, "role": "overview", "core_message": "Key context and objectives", "layout_key": "overview", "content_blocks": [{"type": "bullets", "items": ["Context", "Objective", "Approach"]}]},
            {"number": 3, "role": "insight", "core_message": "The decision is supported by a clear insight", "layout_key": "insight", "content_blocks": [{"type": "bullets", "items": ["Evidence", "Implication", "Recommendation"]}]},
            {"number": 4, "role": "next_steps", "core_message": "A concrete next-step plan", "layout_key": "steps", "content_blocks": [{"type": "bullets", "items": ["Align", "Execute", "Measure"]}]},
        ],
        "image_tasks": [],
    }


def validate_fast_contract(contract: dict[str, Any], project: Path | None = None) -> dict[str, Any]:
    """Validate the compact, intentionally strict Fast contract."""
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"fast_contract.schema must be {CONTRACT_SCHEMA!r}")
    canvas = contract.get("canvas")
    if not isinstance(canvas, dict) or canvas.get("viewBox") != CANVAS["viewBox"]:
        raise ValueError("fast_contract.canvas must use the 1600×900 ppt169 canvas")
    output = str(contract.get("output_name", ""))
    if not output.endswith(".pptx") or not _SAFE_NAME.fullmatch(output):
        raise ValueError("fast_contract.output_name must be a safe .pptx filename")
    slides = contract.get("slides")
    if not isinstance(slides, list) or not 1 <= len(slides) <= 12:
        raise ValueError("fast_contract.slides must contain 1 to 12 pages")
    seen: set[int] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            raise ValueError("every slide must be an object")
        number = slide.get("number")
        if not isinstance(number, int) or number < 1 or number in seen:
            raise ValueError("slide numbers must be unique positive integers")
        seen.add(number)
        if not all(isinstance(slide.get(key), str) and slide[key].strip() for key in ("role", "core_message", "layout_key")):
            raise ValueError("every slide needs role, core_message, and layout_key")
        if not isinstance(slide.get("content_blocks"), list):
            raise ValueError("every slide needs typed content_blocks")
    tasks = contract.get("image_tasks", [])
    if not isinstance(tasks, list) or len(tasks) > PPT_IMAGE_LIMIT:
        raise ValueError(f"fast_contract.image_tasks may contain at most {PPT_IMAGE_LIMIT} tasks")
    if project:
        for source in contract.get("sources", []):
            candidate = (project / str(source)).resolve()
            if project not in candidate.parents and candidate != project:
                raise ValueError("fast_contract source path escapes project")
    return contract


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _fallback_svg(slide: dict[str, Any], contract: dict[str, Any]) -> str:
    palette = contract["palette"]
    title = html.escape(str(slide["core_message"]))
    blocks = slide.get("content_blocks") or []
    lines: list[str] = []
    for block in blocks:
        for text in block.get("items", []) if isinstance(block, dict) else []:
            lines.append(html.escape(str(text)))
        if isinstance(block, dict) and block.get("text") and block.get("type") != "title":
            lines.append(html.escape(str(block["text"])))
    if not lines:
        lines = [html.escape(str(slide.get("role", "Key message")))]
    body = "".join(f'<text x="150" y="{390 + index * 72}" font-family="{html.escape(contract["fonts"]["body"])}" font-size="32" fill="{palette["ink"]}">• {line}</text>' for index, line in enumerate(lines[:5]))
    return f'''<svg xmlns="{_SVG_NS}" width="1600" height="900" viewBox="0 0 1600 900">
  <rect width="1600" height="900" fill="{palette["background"]}"/>
  <rect x="96" y="110" width="14" height="620" rx="7" fill="{palette["accent"]}"/>
  <text x="150" y="220" font-family="{html.escape(contract["fonts"]["heading"])}" font-size="58" font-weight="700" fill="{palette["ink"]}">{title}</text>
  <line x1="150" x2="1440" y1="278" y2="278" stroke="{palette["muted"]}" stroke-opacity="0.35"/>
  {body}
  <text x="150" y="790" font-family="{html.escape(contract["fonts"]["body"])}" font-size="22" fill="{palette["muted"]}">{slide["number"]:02d}</text>
</svg>'''


def _is_valid_svg(content: str) -> bool:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return False
    return root.tag.endswith("svg") and root.get("viewBox") == "0 0 1600 900"


def _message_text(response: Any) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "\n".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in value)
    return str(value)


async def _model_svg(slides: list[dict[str, Any]], contract: dict[str, Any]) -> dict[int, str]:
    """Ask the configured main model once per worker; no DeepAgents subgraph."""
    from agent_core.llm import create_llm

    prompt = (
        "Return only a JSON object mapping slide number to a complete editable SVG string. "
        "Use viewBox exactly `0 0 1600 900`; no external URLs, scripts, or files. "
        "Use simple SVG rect/text/line elements. Global design contract: "
        + json.dumps({key: contract[key] for key in ("canvas", "palette", "fonts", "prototype")}, ensure_ascii=False)
        + ". Assigned slides: " + json.dumps(slides, ensure_ascii=False)
    )
    response = await create_llm().ainvoke(prompt)
    raw = _message_text(response).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    parsed = json.loads(raw)
    return {int(key): str(value) for key, value in parsed.items()}


async def _build_worker(
    assigned: list[dict[str, Any]],
    contract: dict[str, Any],
    output_dir: Path,
    model_worker: Callable[[list[dict[str, Any]], dict[str, Any]], Awaitable[dict[int, str]]] | None,
) -> tuple[list[str], list[str]]:
    generated: dict[int, str] = {}
    if model_worker:
        try:
            generated = await asyncio.wait_for(model_worker(assigned, contract), timeout=PPT_PAGE_TIMEOUT_SECONDS)
        except (TimeoutError, asyncio.TimeoutError, ValueError, json.JSONDecodeError):
            generated = {}
    written, fallback = [], []
    for slide in assigned:
        name = f"slide_{slide['number']:02d}.svg"
        content = generated.get(slide["number"], "")
        if not _is_valid_svg(content):
            content = _fallback_svg(slide, contract)
            fallback.append(name)
        _atomic_write(output_dir / name, content)
        written.append(name)
    return written, fallback


async def _run_image_task(project: Path, task: dict[str, Any]) -> dict[str, Any]:
    """Run only an explicit project-local image command with this interpreter.

    A missing command is an intentional no-image downgrade.  This prevents the
    old behaviour of falling back across providers when the designated image
    request times out.
    """
    command = task.get("command")
    if not isinstance(command, list) or not command:
        return {"id": task.get("id", "image"), "status": "skipped", "reason": "no explicit image command"}
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, *map(str, command), cwd=str(project),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=PPT_PAGE_TIMEOUT_SECONDS)
        if proc.returncode:
            return {"id": task.get("id", "image"), "status": "failed", "reason": stderr.decode("utf-8", "replace")[-500:]}
        return {"id": task.get("id", "image"), "status": "completed"}
    except TimeoutError:
        return {"id": task.get("id", "image"), "status": "timeout"}


async def _render_contact_sheets(project: Path, pages: list[str]) -> list[Path]:
    """Render up to two six-page PNG contact sheets without a preview server."""
    if not pages:
        return []
    try:
        from PIL import Image, ImageDraw
        from playwright.async_api import async_playwright
    except ImportError:
        return []
    preview_dir = project / "validation" / "fast_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                for page_name in pages[:12]:
                    svg = (project / "svg_output" / page_name).read_text(encoding="utf-8")
                    browser_page = await browser.new_page(viewport={"width": 800, "height": 450})
                    try:
                        await browser_page.set_content(f"<style>html,body{{margin:0}}</style>{svg}")
                        target = preview_dir / f"{Path(page_name).stem}.png"
                        await browser_page.screenshot(path=str(target), type="png")
                        rendered.append(target)
                    finally:
                        await browser_page.close()
            finally:
                await browser.close()
    except Exception:
        return []
    sheets: list[Path] = []
    for batch_number, start in enumerate(range(0, len(rendered), 6), start=1):
        batch = rendered[start:start + 6]
        sheet = Image.new("RGB", (1200, 700), "#111827")
        for index, image_path in enumerate(batch):
            with Image.open(image_path) as image:
                frame = image.convert("RGB")
                frame.thumbnail((380, 214))
                x, y = 10 + (index % 3) * 395, 20 + (index // 3) * 335
                sheet.paste(frame, (x, y + 28))
                ImageDraw.Draw(sheet).text((x, y), image_path.stem, fill="#F8FAFC")
        target = preview_dir / f"contact_sheet_{batch_number}.png"
        sheet.save(target)
        sheets.append(target)
    return sheets


async def _review_contact_sheets(sheets: list[Path]) -> str:
    if not sheets:
        return "skipped: static renderer unavailable"
    from tools.review_ppt_images import review_ppt_images

    try:
        paths = [str(path.relative_to(WORKSPACE_ROOT)) for path in sheets]
        return await asyncio.wait_for(
            asyncio.to_thread(
                review_ppt_images.func,
                paths,
                "Review the full deck once. Report only blocking blank pages, missing images, clipping, overlap, overflow, or severe contrast/readability failures. Name the slide filename for every blocking issue.",
                "high",
                PPT_FAST_VISION_TIMEOUT,
            ),
            timeout=PPT_FAST_VISION_TIMEOUT,
        )
    except TimeoutError:
        return "skipped: Qwen visual review timed out"
    except Exception as exc:  # visual QA is an enhancement, not a delivery blocker
        return f"skipped: Qwen visual review unavailable ({type(exc).__name__})"


def _run_quick_checker(project: Path) -> tuple[bool, str]:
    script = SKILLS_DIR / "ppt-master" / "scripts" / "svg_quality_checker.py"
    report = project / "validation" / "svg_quality_report.json"
    proc = subprocess.run(
        [sys.executable, str(script), str(project), "--quick-generate", "--stage", "final", "--json", "--json-output", str(report)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False,
    )
    return proc.returncode == 0, (proc.stderr or proc.stdout)[-2000:]


def _export_pptx(project: Path, output_name: str) -> Path | None:
    script = SKILLS_DIR / "ppt-master" / "scripts" / "svg_to_pptx.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(project), "--quick-generate", "--no-notes"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=55, check=False,
    )
    if proc.returncode:
        return None
    candidates = sorted(project.rglob("*.pptx"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    destination = WORKSPACE_ROOT / "output" / output_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(candidates[0].read_bytes())
    try:
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None:
                destination.unlink(missing_ok=True)
                return None
    except zipfile.BadZipFile:
        destination.unlink(missing_ok=True)
        return None
    return destination


def _reviewed_blocking_pages(review: str, pages: list[str]) -> list[str]:
    """Keep visual QA bounded: only named blocking defects get one repair."""
    lowered = review.lower()
    blocker_words = ("blank", "missing", "clip", "overlap", "overflow", "contrast", "readability", "阻塞", "空白", "缺图", "裁切", "重叠", "溢出")
    if not any(word in lowered for word in blocker_words):
        return []
    names = {f"slide_{int(value):02d}.svg" for value in re.findall(r"slide[_\s-]?(\d{1,2})", lowered)}
    return [name for name in pages if name in names]


async def ppt_fast_build(
    project_path: str,
    *,
    model_worker: Callable[[list[dict[str, Any]], dict[str, Any]], Awaitable[dict[int, str]]] | None = _model_svg,
) -> FastBuildSummary:
    """Build a Fast PPT project with four isolated workers and safe fallbacks."""
    started = time.monotonic()
    project = _project_path(project_path)
    contract_path = project / "fast_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.exists() else _default_contract(project)
    validate_fast_contract(contract, project)
    if not contract_path.exists():
        _atomic_write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2) + "\n")
    contract_finished = time.monotonic()
    output_dir = project / "svg_output"
    output_dir.mkdir(exist_ok=True)
    (project / "validation").mkdir(exist_ok=True)
    workers = min(PPT_PAGE_CONCURRENCY, len(contract["slides"]))
    assignments = [contract["slides"][index::workers] for index in range(workers)]
    page_jobs = [_build_worker(group, contract, output_dir, model_worker) for group in assignments]
    image_semaphore = asyncio.Semaphore(PPT_IMAGE_CONCURRENCY)

    async def bounded_image_task(task: dict[str, Any]) -> dict[str, Any]:
        async with image_semaphore:
            return await _run_image_task(project, task)

    image_jobs = [bounded_image_task(task) for task in contract.get("image_tasks", [])]
    page_results, image_results = await asyncio.gather(
        asyncio.gather(*page_jobs),
        asyncio.gather(*image_jobs) if image_jobs else asyncio.sleep(0, result=[]),
    )
    authoring_finished = time.monotonic()
    pages = sorted(name for names, _ in page_results for name in names)
    fallbacks = sorted(name for _, names in page_results for name in names)
    summary = FastBuildSummary(
        project_path=str(project), contract_path=str(contract_path), workers=workers, pages=pages,
        image_results=image_results, fallback_pages=fallbacks,
        page_concurrency=workers, image_concurrency=min(PPT_IMAGE_CONCURRENCY, len(image_jobs)),
    )
    passed, detail = _run_quick_checker(project)
    if not passed:
        summary.blocking_issues.append(detail or "quick SVG checker failed")
        # Every worker output already has one safe fallback. Rewrite every page once
        # so malformed external assets or a failed model response cannot block export.
        for slide in contract["slides"]:
            name = f"slide_{slide['number']:02d}.svg"
            _atomic_write(output_dir / name, _fallback_svg(slide, contract))
        summary.fallback_pages = sorted(set(summary.fallback_pages + pages))
        passed, detail = _run_quick_checker(project)
        if not passed:
            summary.blocking_issues = [detail or "safe-layout checker failed"]
    sheets = await _render_contact_sheets(project, pages)
    summary.review = await _review_contact_sheets(sheets)
    repaired = _reviewed_blocking_pages(summary.review, pages)
    if repaired:
        by_name = {f"slide_{slide['number']:02d}.svg": slide for slide in contract["slides"]}
        await asyncio.gather(*[
            asyncio.to_thread(_atomic_write, output_dir / name, _fallback_svg(by_name[name], contract))
            for name in repaired
        ])
        summary.repaired_pages = repaired
    # The final gate is deliberately repeated after the single repair decision.
    passed, detail = _run_quick_checker(project)
    if not passed:
        summary.blocking_issues = [detail or "final SVG checker failed"]
    qa_finished = time.monotonic()
    if passed:
        summary.output_path = str(_export_pptx(project, contract["output_name"]) or "") or None
        if summary.output_path is None:
            summary.blocking_issues.append("PPTX export failed")
    export_finished = time.monotonic()
    summary.elapsed_seconds = round(export_finished - started, 3)
    summary.phase_seconds = {
        "contract_and_sources": round(contract_finished - started, 3),
        "parallel_pages_and_images": round(authoring_finished - contract_finished, 3),
        "static_and_visual_qa": round(qa_finished - authoring_finished, 3),
        "repair_and_export": round(export_finished - qa_finished, 3),
    }
    report = project / "validation" / "fast_run.json"
    _atomic_write(report, json.dumps(summary.as_dict(), ensure_ascii=False, indent=2) + "\n")
    return summary


@tool("ppt_fast_build")
async def ppt_fast_build_tool(project_path: str) -> dict[str, Any]:
    """Fast-generate a standard editable PPTX project without confirmation UI."""
    summary = await asyncio.wait_for(ppt_fast_build(project_path), timeout=PPT_FAST_DEADLINE_SECONDS)
    return summary.as_dict()


__all__ = ["FastBuildSummary", "ppt_fast_build", "ppt_fast_build_tool", "validate_fast_contract"]
