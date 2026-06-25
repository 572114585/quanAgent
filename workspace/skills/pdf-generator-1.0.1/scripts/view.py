#!/usr/bin/env python3
"""Inspect (read back) a PDF file for verification.

Part of the pdf-generator skill. Read-only — never modifies the file.

    python skills/pdf-generator-1.0.1/scripts/view.py --file output/report.pdf
    python skills/pdf-generator-1.0.1/scripts/view.py --file output/report.pdf --extract-text --max-pages 5

NOTE: this file is intentionally named `view.py`, not `inspect.py`, to avoid
shadowing the Python standard-library `inspect` module.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
except ImportError:
    print("ERROR: pypdf (or PyPDF2) is not installed. Run: pip install pypdf", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a PDF document (pdf-generator skill, read-only).",
    )
    parser.add_argument("--file", required=True, help="PDF path to inspect (workspace-relative).")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to extract text from (default 3).")
    parser.add_argument(
        "--extract-text",
        action="store_true",
        help="Extract and print text content from pages.",
    )
    parser.add_argument("--list-pages", action="store_true", help="Only list page count and exit.")
    parser.add_argument(
        "--show-metadata",
        action="store_true",
        help="Show full document metadata.",
    )
    args = parser.parse_args()

    file_path = _resolve_path(args.file)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        return 2

    try:
        reader = PdfReader(str(file_path))
    except Exception as e:
        print(f"ERROR: cannot read PDF: {e}", file=sys.stderr)
        return 2

    file_size = file_path.stat().st_size
    print(f"file: {file_path}")
    print(f"size: {file_size:,} bytes")
    print(f"pages: {len(reader.pages)}")

    meta = reader.metadata
    if meta:
        if args.show_metadata:
            print("\nmetadata:")
            for key, value in meta.items():
                if value:
                    print(f"  {key}: {value}")
        else:
            title = meta.get("/Title", "")
            author = meta.get("/Author", "")
            creator = meta.get("/Creator", "")
            if title:
                print(f"title: {title}")
            if author:
                print(f"author: {author}")
            if creator:
                print(f"creator: {creator}")

    if args.list_pages:
        return 0

    if args.extract_text:
        limit = max(0, args.max_pages)
        print(f"\ntext (first {min(limit, len(reader.pages))} pages):")
        print("-" * 60)
        for i, page in enumerate(reader.pages[:limit]):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = "[text extraction failed for this page]"
            print(f"\n--- Page {i+1} ---")
            if len(text) > 2000:
                print(text[:2000] + "...")
            else:
                print(text if text else "[empty or image-based page]")
        if len(reader.pages) > limit:
            print(f"\n... ({len(reader.pages) - limit} more pages not shown)")

    return 0


def _resolve_path(arg: str) -> Path:
    if arg.startswith("/"):
        return Path(arg.lstrip("/"))
    return Path(arg)


if __name__ == "__main__":
    raise SystemExit(main())
