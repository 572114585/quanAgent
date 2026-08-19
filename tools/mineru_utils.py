"""Bounded adapter for the workspace MinerU skill.

PDF/document parsing is delegated to the user-provided skill wrapper.  This
module only supplies safe process invocation, deterministic caching, output
validation, and provenance; it contains no fallback PDF parser.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from agent_core.config import WORKSPACE_ROOT


_TOKEN_RE = re.compile(r"(--token\s+)\S+", re.IGNORECASE)


@dataclass(frozen=True)
class MinerUResult:
    content: str = ""
    mode: str = ""
    output_path: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.content.strip()) and not self.error


def _safe_error(value: str) -> str:
    redacted = _TOKEN_RE.sub(r"\1[REDACTED]", value or "")
    return " ".join(redacted.split())[-800:]


def _input_identity(value: str | Path) -> tuple[str, str]:
    raw = str(value)
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        return raw, f"url:{raw}"
    target = Path(value).resolve()
    workspace = Path(WORKSPACE_ROOT).resolve()
    if target != workspace and workspace not in target.parents:
        raise ValueError("MinerU local input must stay within the workspace")
    relative = target.relative_to(workspace).as_posix()
    stat = target.stat()
    return relative, f"file:{relative}:{stat.st_size}:{stat.st_mtime_ns}"


def extract_with_mineru(
    value: str | Path,
    *,
    language: str = "ch",
    ocr: bool = False,
    timeout: int | None = None,
) -> MinerUResult:
    """Run ``skills/mineru/scripts/extract.py`` and return validated Markdown."""
    workspace = Path(WORKSPACE_ROOT).resolve()
    script = workspace / "skills" / "mineru" / "scripts" / "extract.py"
    if not script.is_file():
        return MinerUResult(error="mineru_skill_missing")
    try:
        input_arg, identity = _input_identity(value)
    except (OSError, ValueError) as exc:
        return MinerUResult(error=f"mineru_input_invalid:{type(exc).__name__}:{exc}")

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    relative_output = Path("output") / "mineru-cache" / f"{digest}.md"
    output = workspace / relative_output
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached = output.read_text(encoding="utf-8") if output.is_file() else ""
    except OSError:
        cached = ""
    if len(cached.strip()) >= 80 and not cached.lstrip().startswith("%PDF-"):
        return MinerUResult(
            content=cached,
            mode="cache",
            output_path=relative_output.as_posix(),
        )

    limit = timeout if timeout is not None else int(os.getenv("MINERU_EXTRACT_TIMEOUT", "900"))
    limit = max(30, min(int(limit), 1800))
    command = [
        sys.executable,
        "skills/mineru/scripts/extract.py",
        input_arg,
        "-o",
        relative_output.as_posix(),
        "--language",
        language,
        "--timeout",
        str(limit),
    ]
    if ocr:
        command.append("--ocr")
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=limit + 30,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return MinerUResult(error=f"mineru_timeout:{limit}s")
    except OSError as exc:
        return MinerUResult(error=f"mineru_process_failed:{type(exc).__name__}")
    if completed.returncode != 0:
        detail = completed.stderr or completed.stdout or f"exit_{completed.returncode}"
        return MinerUResult(error=f"mineru_failed:{_safe_error(detail)}")
    try:
        content = output.read_text(encoding="utf-8")
    except OSError as exc:
        return MinerUResult(error=f"mineru_output_missing:{type(exc).__name__}")
    if len(content.strip()) < 80 or content.lstrip().startswith("%PDF-"):
        return MinerUResult(error="mineru_output_unusable")
    diagnostics = f"{completed.stderr}\n{completed.stdout}".casefold()
    mode = "flash-extract" if "flash-extract" in diagnostics else "extract"
    return MinerUResult(
        content=content,
        mode=mode,
        output_path=relative_output.as_posix(),
    )
