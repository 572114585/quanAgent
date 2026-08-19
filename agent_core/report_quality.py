"""Deterministic final-report quality checks and rubric scoring."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import unescape
from pathlib import Path
from typing import Iterable, Literal


_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_HTML_RE = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.I | re.S)
_PARAGRAPH_HTML_RE = re.compile(r"<(?:p|li|td|blockquote)\b[^>]*>(.*?)</(?:p|li|td|blockquote)>", re.I | re.S)
_PLACEHOLDER_RE = re.compile(r"\{\{(?:chart|table|flowchart|concept-map|timeline|comparison-matrix|data-card|quote):.*?\}\}", re.I | re.S)
_TODO_RE = re.compile(r"(?:\bTODO\b|\bTBD\b|\[此处需要补充[:：].*?\])", re.I)
_URL_RE = re.compile(r"https?://[^\s<>)\]]+", re.I)
_NUMERIC_CITATION_RE = re.compile(r"(?<!\!)\[(\d{1,3})\]")
_MARKDOWN_REFERENCE_RE = re.compile(r"(?m)^\s*(?:\|\s*)?\[(\d{1,3})\](?:\s*\||\s*:)")
_HTML_REFERENCE_RE = re.compile(r"<td[^>]*>\s*\[(\d{1,3})\]\s*</td>", re.I)
_STALE_FORECAST_RE = re.compile(
    r"(?P<year>20\d{2})年(?:上|下)半年[^。\n]{0,180}(?:将|预计|有望|未来)", re.I
)


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", value))).strip()


def _contains(text: str, pattern: str) -> bool:
    try:
        return re.search(pattern, text, re.I) is not None
    except re.error:
        return pattern.lower() in text.lower()


@dataclass(frozen=True)
class KeyPoint:
    key: str
    patterns: tuple[str, ...]
    weight: float = 1.0


@dataclass
class ReportContract:
    required_key_points: list[KeyPoint] = field(default_factory=list)
    priority_topics: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    require_executive_summary: bool = True
    require_source_urls: bool = True
    min_priority_paragraph_share: float = 0.12
    max_heading_to_paragraph_ratio: float = 0.55


@dataclass
class ReportQualityResult:
    ok: bool
    format: Literal["markdown", "html"]
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, float | int]
    missing_key_points: list[str]


def evaluate_report_quality(
    content: str,
    contract: ReportContract | None = None,
    *,
    current_date: date | None = None,
) -> ReportQualityResult:
    contract = contract or ReportContract()
    current_date = current_date or date.today()
    is_html = bool(re.search(r"<(?:html|body|h1|p)\b", content, re.I))
    fmt: Literal["markdown", "html"] = "html" if is_html else "markdown"
    plain = _plain(content) if is_html else content
    headings = (
        [_plain(item) for item in _HEADING_HTML_RE.findall(content)]
        if is_html
        else re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", content)
    )
    paragraphs = (
        [_plain(item) for item in _PARAGRAPH_HTML_RE.findall(content) if len(_plain(item)) >= 20]
        if is_html
        else [
            re.sub(r"\s+", " ", item).strip()
            for item in re.split(
                r"\n\s*\n",
                re.sub(r"(?m)^#{1,6}\s+.+?\s*$", "", content),
            )
            if len(re.sub(r"[#|>*_`\-\s]", "", item)) >= 20
        ]
    )

    errors: list[str] = []
    warnings: list[str] = []
    placeholder_count = len(_PLACEHOLDER_RE.findall(content))
    todo_count = len(_TODO_RE.findall(content))
    if placeholder_count:
        errors.append(f"report contains {placeholder_count} unresolved presentation placeholder(s)")
    if todo_count:
        errors.append(f"report contains {todo_count} TODO/TBD marker(s)")

    cited = {int(item) for item in _NUMERIC_CITATION_RE.findall(content)}
    defined = {
        int(item)
        for item in (
            _HTML_REFERENCE_RE.findall(content) if is_html else _MARKDOWN_REFERENCE_RE.findall(content)
        )
    }
    missing_citations = sorted(cited - defined)
    if missing_citations:
        errors.append("unresolved numeric citations: " + ", ".join(map(str, missing_citations)))
    url_count = len(_URL_RE.findall(content))
    if contract.require_source_urls and cited and url_count == 0:
        errors.append("report cites external facts but contains no source URL")

    heading_ratio = len(headings) / max(len(paragraphs), 1)
    if heading_ratio > contract.max_heading_to_paragraph_ratio:
        warnings.append(
            f"heading/paragraph ratio {heading_ratio:.3f} suggests fragmented catalogue-style writing"
        )
    if contract.require_executive_summary and not any(
        re.search(r"(?:执行摘要|核心结论|研究结论|executive summary)", item, re.I)
        for item in headings[:12]
    ):
        errors.append("report has no early executive-summary/core-conclusions section")

    total_weight = sum(max(point.weight, 0) for point in contract.required_key_points)
    recalled_weight = 0.0
    missing_key_points: list[str] = []
    for point in contract.required_key_points:
        if any(_contains(plain, pattern) for pattern in point.patterns):
            recalled_weight += max(point.weight, 0)
        else:
            missing_key_points.append(point.key)
    key_point_recall = recalled_weight / max(total_weight, 1.0) if total_weight else 1.0
    if missing_key_points:
        errors.append("missing required key points: " + ", ".join(missing_key_points))

    priority_chars = sum(
        len(paragraph)
        for paragraph in paragraphs
        if any(_contains(paragraph, topic) for topic in contract.priority_topics)
    )
    paragraph_chars = sum(len(item) for item in paragraphs)
    priority_share = priority_chars / max(paragraph_chars, 1) if contract.priority_topics else 1.0
    if contract.priority_topics and priority_share < contract.min_priority_paragraph_share:
        errors.append(
            f"priority-topic paragraph share {priority_share:.3f} is below {contract.min_priority_paragraph_share:.3f}"
        )

    excluded_hits = [topic for topic in contract.excluded_topics if _contains(plain, topic)]
    if excluded_hits:
        warnings.append("out-of-scope topics are present: " + ", ".join(excluded_hits))
    forbidden_hits = [claim for claim in contract.forbidden_claims if _contains(plain, claim)]
    if forbidden_hits:
        errors.append("forbidden/overstated claims are present: " + ", ".join(forbidden_hits))

    stale_forecasts = [
        match.group(0) for match in _STALE_FORECAST_RE.finditer(plain)
        if int(match.group("year")) < current_date.year
    ]
    if stale_forecasts:
        errors.append(f"report contains {len(stale_forecasts)} forecast(s) whose horizon is already past")

    metrics: dict[str, float | int] = {
        "headings": len(headings),
        "paragraphs": len(paragraphs),
        "heading_to_paragraph_ratio": round(heading_ratio, 4),
        "placeholders": placeholder_count,
        "todos": todo_count,
        "numeric_citations": len(cited),
        "defined_numeric_references": len(defined),
        "source_urls": url_count,
        "weighted_key_point_recall": round(key_point_recall, 4),
        "priority_paragraph_share": round(priority_share, 4),
        "stale_forecasts": len(stale_forecasts),
    }
    return ReportQualityResult(
        ok=not errors,
        format=fmt,
        errors=errors,
        warnings=warnings,
        metrics=metrics,
        missing_key_points=missing_key_points,
    )


def evaluate_report_file(path: Path, contract: ReportContract | None = None) -> ReportQualityResult:
    return evaluate_report_quality(path.read_text(encoding="utf-8"), contract)
