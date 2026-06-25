#!/usr/bin/env python3
"""Edit, merge, split, or add metadata to existing PDF files.

Part of the pdf-generator skill. Invoked by the agent via the `execute` tool:

Merge PDFs:
    python skills/pdf-generator-1.0.1/scripts/edit.py --merge --files '["a.pdf","b.pdf"]' --out output/merged.pdf

Split PDF (extract pages):
    python skills/pdf-generator-1.0.1/scripts/edit.py --split --file input.pdf --pages '0,2' --out output/split.pdf

Set metadata:
    python skills/pdf-generator-1.0.1/scripts/edit.py --meta --file input.pdf --title "New Title" --author "Name" --out output/updated.pdf

Add watermark text:
    python skills/pdf-generator-1.0.1/scripts/edit.py --watermark --file input.pdf --text "CONFIDENTIAL" --out output/watermarked.pdf
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    print("ERROR: pypdf (or PyPDF2) is not installed. Run: pip install pypdf", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Edit PDF files (pdf-generator skill): merge, split, set metadata, or watermark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--merge", action="store_true", help="Merge multiple PDFs into one.")
    action_group.add_argument("--split", action="store_true", help="Extract specific pages from a PDF.")
    action_group.add_argument("--meta", action="store_true", help="Update PDF metadata (title/author/subject).")
    action_group.add_argument("--watermark", action="store_true", help="Add text watermark to all pages.")

    parser.add_argument("--file", help="Input PDF file path (for split/meta/watermark).")
    parser.add_argument("--files", help='JSON array of PDF paths to merge, e.g. \'["a.pdf","b.pdf"]\'.')
    parser.add_argument("--out", required=True, help="Output PDF path (workspace-relative).")
    parser.add_argument(
        "--pages",
        default=None,
        help='Page indices to extract (0-based, comma-separated), e.g. "0,2,4" or range "0:3".',
    )
    parser.add_argument("--title", default=None, help="Set document title metadata.")
    parser.add_argument("--author", default=None, help="Set document author metadata.")
    parser.add_argument("--subject", default=None, help="Set document subject metadata.")
    parser.add_argument("--text", default=None, help="Watermark text (for --watermark).")
    parser.add_argument(
        "--watermark-opacity",
        type=float,
        default=0.3,
        help="Watermark opacity 0.0-1.0 (default 0.3).",
    )
    args = parser.parse_args()

    out_path = _resolve_path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.merge:
        return _do_merge(args, out_path)
    elif args.split:
        return _do_split(args, out_path)
    elif args.meta:
        return _do_meta(args, out_path)
    elif args.watermark:
        return _do_watermark(args, out_path)
    return 1


def _parse_page_spec(spec: str, total_pages: int) -> list[int]:
    """Parse page specification like '0,2,4' or '0:3' or ':5' into 0-based indices."""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            start_str, end_str = part.split(":", 1)
            start = int(start_str) if start_str.strip() else 0
            end = int(end_str) if end_str.strip() else total_pages
            pages.extend(range(max(0, start), min(total_pages, end)))
        else:
            idx = int(part)
            if 0 <= idx < total_pages:
                pages.append(idx)
    return sorted(set(pages))


def _do_merge(args, out_path: Path) -> int:
    if not args.files:
        print("ERROR: --files is required for --merge (JSON array of PDF paths).", file=sys.stderr)
        return 2
    try:
        file_list = json.loads(args.files)
    except json.JSONDecodeError as e:
        print(f"ERROR: --files is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(file_list, list) or not file_list:
        print("ERROR: --files must be a non-empty JSON array of paths.", file=sys.stderr)
        return 2

    writer = PdfWriter()
    total_pages = 0
    for f in file_list:
        pdf_path = _resolve_path(str(f))
        if not pdf_path.exists():
            print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
            return 2
        try:
            reader = PdfReader(str(pdf_path))
            for page in reader.pages:
                writer.add_page(page)
            total_pages += len(reader.pages)
        except Exception as e:
            print(f"ERROR: cannot read {pdf_path}: {e}", file=sys.stderr)
            return 2

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"OK merged: {out_path}")
    print(f"  files: {len(file_list)}")
    print(f"  total pages: {total_pages}")
    return 0


def _do_split(args, out_path: Path) -> int:
    if not args.file:
        print("ERROR: --file is required for --split.", file=sys.stderr)
        return 2
    if not args.pages:
        print("ERROR: --pages is required for --split (e.g. '0,2' or '0:5').", file=sys.stderr)
        return 2
    pdf_path = _resolve_path(args.file)
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"ERROR: cannot read PDF: {e}", file=sys.stderr)
        return 2

    pages = _parse_page_spec(args.pages, len(reader.pages))
    if not pages:
        print("ERROR: no valid pages specified.", file=sys.stderr)
        return 2

    writer = PdfWriter()
    for idx in pages:
        writer.add_page(reader.pages[idx])

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"OK split: {out_path}")
    print(f"  extracted pages: {[p+1 for p in pages]} (1-based)")
    print(f"  output pages: {len(pages)}")
    return 0


def _do_meta(args, out_path: Path) -> int:
    if not args.file:
        print("ERROR: --file is required for --meta.", file=sys.stderr)
        return 2
    if not any([args.title, args.author, args.subject]):
        print("ERROR: at least one of --title/--author/--subject required for --meta.", file=sys.stderr)
        return 2
    pdf_path = _resolve_path(args.file)
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"ERROR: cannot read PDF: {e}", file=sys.stderr)
        return 2

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    metadata = {}
    if args.title:
        metadata["/Title"] = args.title
    if args.author:
        metadata["/Author"] = args.author
    if args.subject:
        metadata["/Subject"] = args.subject
    if metadata:
        writer.add_metadata(metadata)

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"OK metadata updated: {out_path}")
    print(f"  pages: {len(reader.pages)}")
    for k, v in metadata.items():
        print(f"  {k[1:].lower()}: {v}")
    return 0


def _find_font_path() -> str | None:
    from pathlib import Path
    font_candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for fp in font_candidates:
        if Path(fp).exists():
            return fp
    return None


def _do_watermark(args, out_path: Path) -> int:
    if not args.file:
        print("ERROR: --file is required for --watermark.", file=sys.stderr)
        return 2
    if not args.text:
        print("ERROR: --text is required for --watermark.", file=sys.stderr)
        return 2
    pdf_path = _resolve_path(args.file)
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        from fpdf import FPDF
    except ImportError:
        print("ERROR: fpdf2 is required for watermark. Run: pip install fpdf2", file=sys.stderr)
        return 2

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"ERROR: cannot read PDF: {e}", file=sys.stderr)
        return 2

    first_page = reader.pages[0]
    media_box = first_page.mediabox
    page_width = float(media_box.width)
    page_height = float(media_box.height)

    wm_pdf = FPDF(orientation="P", unit="pt", format=(page_width, page_height))
    font_path = _find_font_path()
    wm_font = "Helvetica"
    if font_path:
        try:
            wm_pdf.add_font("wmfont", "", font_path)
            wm_font = "wmfont"
        except Exception:
            pass
    wm_pdf.add_page()
    wm_pdf.set_font(wm_font, "", 60)
    wm_pdf.set_text_color(128, 128, 128)
    wm_pdf.set_alpha(args.watermark_opacity)
    wm_pdf.rotate(45, wm_pdf.w / 2, wm_pdf.h / 2)
    text_width = wm_pdf.get_string_width(args.text)
    wm_pdf.text((wm_pdf.w - text_width) / 2, wm_pdf.h / 2, args.text)

    import io
    wm_bytes = io.BytesIO()
    wm_pdf.output(wm_bytes)
    wm_bytes.seek(0)
    wm_reader = PdfReader(wm_bytes)
    wm_page = wm_reader.pages[0]

    writer = PdfWriter()
    for page in reader.pages:
        page.merge_page(wm_page)
        writer.add_page(page)

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"OK watermarked: {out_path}")
    print(f"  pages: {len(reader.pages)}")
    print(f"  watermark text: {args.text}")
    print(f"  opacity: {args.watermark_opacity}")
    return 0


def _resolve_path(arg: str) -> Path:
    p = Path(arg)
    if p.exists() or p.is_absolute() and len(p.parts) > 1 and not arg.startswith("/"):
        return p
    if arg.startswith("/"):
        return Path(arg.lstrip("/"))
    return p


if __name__ == "__main__":
    raise SystemExit(main())
