"""Final-report delivery gate exposed as a LangChain tool."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agent_core.report_quality import KeyPoint, ReportContract, evaluate_report_file


def _workspace_path(file_path: str) -> Path:
    from agent_core.config import WORKSPACE_ROOT

    raw = file_path.strip().replace("\\", "/")
    if raw.startswith("/"):
        raw = raw[1:]
    candidate = (WORKSPACE_ROOT / raw).resolve()
    root = WORKSPACE_ROOT.resolve()
    candidate.relative_to(root)
    if not candidate.is_file():
        raise FileNotFoundError(f"report file does not exist: {file_path}")
    return candidate


@tool
def check_final_report(
    file_path: str,
    required_key_points: list[dict[str, Any]] | None = None,
    priority_topics: list[str] | None = None,
    excluded_topics: list[str] | None = None,
    forbidden_claims: list[str] | None = None,
    require_source_urls: bool = True,
) -> str:
    """Check a Markdown/HTML report for evidence, focus, citation, and rendering defects."""
    try:
        points = [
            KeyPoint(
                key=str(item["key"]),
                patterns=tuple(str(value) for value in item.get("patterns", []) if str(value).strip()),
                weight=float(item.get("weight", 1.0)),
            )
            for item in (required_key_points or [])
        ]
        contract = ReportContract(
            required_key_points=points,
            priority_topics=priority_topics or [],
            excluded_topics=excluded_topics or [],
            forbidden_claims=forbidden_claims or [],
            require_source_urls=require_source_urls,
        )
        result = evaluate_report_file(_workspace_path(file_path), contract)
        return json.dumps({
            "ok": result.ok,
            "file_path": file_path,
            "errors": result.errors,
            "warnings": result.warnings,
            "metrics": result.metrics,
            "missing_key_points": result.missing_key_points,
        }, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "file_path": file_path, "error": str(exc)}, ensure_ascii=False, indent=2)
