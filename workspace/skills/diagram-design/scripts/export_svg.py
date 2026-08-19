#!/usr/bin/env python3
"""Extract the first diagram <svg> from a generated HTML file into a standalone SVG.

DeepAgent replacement for the upstream Playwright / python -c export path:

    python skills/diagram-design/scripts/export_svg.py --file output/arch.html --out output/arch.svg
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
    "&amp;family=Geist:wght@400;500;600&amp;family=Geist+Mono:wght@400;500;600&amp;display=swap');"
)
FONT_STYLE = f"<style>{FONT_IMPORT}</style>"
_ALLOWED_WRITE = frozenset({"output", "tmp"})
_ALLOWED_READ = frozenset({"output", "tmp", "skills", "uploads"})
_SVG_OPEN = re.compile(r"<svg\b", re.IGNORECASE)


def _posix(path: Path) -> str:
    return path.as_posix().replace("\\", "/")


def _under_allowed(path: Path, allowed: frozenset[str]) -> bool:
    parts = Path(_posix(path)).parts
    if ".." in parts:
        return False
    return bool(parts) and parts[0] in allowed


def _extract_first_svg(html: str) -> str | None:
    match = _SVG_OPEN.search(html)
    if match is None:
        return None
    start = match.start()
    depth = 0
    pos = start
    lower = html.lower()
    while True:
        open_at = lower.find("<svg", pos)
        close_at = lower.find("</svg>", pos)
        if close_at < 0:
            return None
        if open_at >= 0 and open_at < close_at:
            depth += 1
            pos = open_at + 4
            continue
        depth -= 1
        end = close_at + len("</svg>")
        if depth == 0:
            return html[start:end]
        pos = end


def _ensure_xmlns(svg: str) -> str:
    opening_end = svg.find(">")
    if opening_end < 0:
        return svg
    opening = svg[:opening_end]
    if "xmlns=" in opening:
        return svg
    return opening + ' xmlns="http://www.w3.org/2000/svg"' + svg[opening_end:]


def _inject_fonts(svg: str) -> str:
    if "fonts.googleapis.com" in svg:
        return svg
    defs_open = re.search(r"<defs\b[^>]*>", svg, re.IGNORECASE)
    if defs_open:
        insert_at = defs_open.end()
        return svg[:insert_at] + FONT_STYLE + svg[insert_at:]
    # Insert <defs> after the opening <svg ...> tag.
    opening_end = svg.find(">")
    if opening_end < 0:
        return svg
    return svg[: opening_end + 1] + f"<defs>{FONT_STYLE}</defs>" + svg[opening_end + 1 :]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract a standalone SVG from a diagram HTML file (diagram-design skill).",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Source HTML path (workspace-relative, e.g. output/arch.html).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output SVG path (must be under output/ or tmp/).",
    )
    args = parser.parse_args()

    src = Path(args.file)
    dest = Path(args.out)
    if src.is_absolute() or dest.is_absolute():
        print("export_svg: refuse absolute paths; use workspace-relative output/ or tmp/.", file=sys.stderr)
        return 2
    if not _under_allowed(src, _ALLOWED_READ):
        print(f"export_svg: refuse read path {src}; must be under output/, tmp/, skills/, or uploads/.", file=sys.stderr)
        return 2
    if not _under_allowed(dest, _ALLOWED_WRITE):
        print(f"export_svg: refuse write path {dest}; must be under output/ or tmp/.", file=sys.stderr)
        return 2
    if src.name == "index.html" and "assets" in src.parts:
        print("export_svg: refuse gallery assets/index.html; pick a specific diagram file.", file=sys.stderr)
        return 2
    if not src.is_file():
        print(f"export_svg: source not found: {src}", file=sys.stderr)
        return 2

    html = src.read_text(encoding="utf-8")
    svg = _extract_first_svg(html)
    if not svg:
        print("export_svg: no <svg> block found; source is not a diagram file.", file=sys.stderr)
        return 2
    if re.search(r"\bviewBox\s*=", svg, re.IGNORECASE) is None:
        print("export_svg: warning: SVG has no viewBox; writing anyway.", file=sys.stderr)

    svg = _ensure_xmlns(svg)
    svg = _inject_fonts(svg)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + svg + "\n", encoding="utf-8")
    print(f"Wrote {dest.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
