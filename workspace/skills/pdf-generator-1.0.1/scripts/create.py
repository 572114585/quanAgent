#!/usr/bin/env python3
"""Create a new PDF document with title, headings, paragraphs, bullets, tables, images, or from Markdown/HTML.

Part of the pdf-generator skill. Invoked by the agent via the `execute` tool:

    python skills/pdf-generator-1.0.1/scripts/create.py --out output/report.pdf --md-file output/doc.md

Design notes:
- Uses fpdf2 for cross-platform pure-Python PDF generation (no system dependencies).
- Supports Chinese text via auto-detected system fonts with graceful fallback.
- Supports Markdown with embedded images (![](path)), headings, paragraphs, lists, tables, bold/italic.
- Uses --blocks for interleaved content (same pattern as word-docx skill).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: fpdf2 is not installed. Run: pip install fpdf2", file=sys.stderr)
    sys.exit(2)


FONT_FAMILY_ATTR = "_font_family"
_WORKSPACE_ROOT: Path | None = None


def _get_search_roots(md_file_path: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    script_dir = Path(__file__).resolve().parent

    if _WORKSPACE_ROOT is not None:
        roots.append(_WORKSPACE_ROOT)
        roots.append(_WORKSPACE_ROOT / "workspace")

    auto_roots = [
        Path.cwd(),
        Path.cwd() / "workspace",
        script_dir.parent.parent.parent.parent,
        script_dir.parent.parent.parent.parent / "workspace",
        script_dir.parent.parent.parent,
        script_dir.parent.parent.parent / "workspace",
    ]

    if md_file_path is not None:
        roots.append(md_file_path.parent)
        roots.append(md_file_path.parent.parent)
        roots.append(md_file_path.parent.parent.parent)

    for r in auto_roots:
        try:
            r_resolved = r.resolve()
            if r_resolved not in roots:
                roots.append(r_resolved)
        except OSError:
            continue

    return roots


class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_table = False

    def header(self):
        font_family = getattr(self, FONT_FAMILY_ATTR, "Helvetica")
        if hasattr(self, '_document_title') and self._document_title:
            self.set_font(font_family, "", 10)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, self._document_title, align="C", new_x="LMARGIN", new_y="NEXT")
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)

    def footer(self):
        font_family = getattr(self, FONT_FAMILY_ATTR, "Helvetica")
        self.set_y(-15)
        self.set_font(font_family, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _register_font(pdf: PDF) -> str:
    font_candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path_str in font_candidates:
        font_path = Path(font_path_str)
        if font_path.exists():
            try:
                pdf.add_font("docfont", "", str(font_path))
                pdf.add_font("docfont", "B", str(font_path))
                setattr(pdf, FONT_FAMILY_ATTR, "docfont")
                return "docfont"
            except Exception:
                continue
    setattr(pdf, FONT_FAMILY_ATTR, "Helvetica")
    return "Helvetica"


def _resolve_asset_path(asset_ref: str, md_file_path: Path | None = None) -> Path | None:
    if not asset_ref:
        return None

    if asset_ref.startswith(("http://", "https://", "data:")):
        return None

    asset_ref_clean = asset_ref.strip().replace("/", "\\")
    is_root_style = asset_ref_clean.startswith("\\")
    if is_root_style:
        asset_ref_clean = asset_ref_clean.lstrip("\\")

    p = Path(asset_ref_clean)

    if p.is_absolute() and p.exists():
        return p

    search_roots = _get_search_roots(md_file_path)
    candidates = []

    for root in search_roots:
        if is_root_style:
            candidates.append(root / p)
            candidates.append(root / "workspace" / p)
            candidates.append(root / "output" / p)
        else:
            candidates.append(root / p)
        if md_file_path is not None:
            candidates.append(md_file_path.parent / p)

    for c in candidates:
        try:
            c_resolved = c.resolve()
            if c_resolved.exists() and c_resolved.is_file():
                return c_resolved
        except OSError:
            continue

    return None


def _add_image(pdf: PDF, img_path: Path, font_family: str, max_width_mm: float = 170):
    w_px, h_px = None, None
    try:
        from PIL import Image
        img = Image.open(str(img_path))
        w_px, h_px = img.size
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.close()
    except Exception:
        try:
            import struct
            with open(str(img_path), 'rb') as f:
                header = f.read(32)
                if header[:8] == b'\x89PNG\r\n\x1a\n':
                    w_px = struct.unpack('>I', header[16:20])[0]
                    h_px = struct.unpack('>I', header[20:24])[0]
                elif header[:2] == b'\xff\xd8':
                    f.seek(0)
                    data = f.read()
                    idx = 2
                    while idx < len(data):
                        while idx < len(data) and data[idx] != 0xFF:
                            idx += 1
                        while idx < len(data) and data[idx] == 0xFF:
                            idx += 1
                        if idx >= len(data):
                            break
                        marker = data[idx]
                        idx += 1
                        if 0xC0 <= marker <= 0xCF and marker != 0xC8:
                            h_px = struct.unpack('>H', data[idx+2:idx+4])[0]
                            w_px = struct.unpack('>H', data[idx+4:idx+6])[0]
                            break
                        else:
                            seglen = struct.unpack('>H', data[idx:idx+2])[0]
                            idx += seglen
        except Exception:
            pass

    if w_px and h_px:
        aspect = h_px / w_px
    else:
        aspect = 0.75

    display_w = min(max_width_mm, pdf.epw)
    display_h = display_w * aspect
    available_h = pdf.h - pdf.get_y() - pdf.b_margin
    if display_h > available_h - 20:
        pdf.add_page()
        available_h = pdf.h - pdf.get_y() - pdf.b_margin
    if display_h > available_h - 20:
        scale = (available_h - 20) / display_h
        display_h = display_h * scale
        display_w = display_w * scale

    x_center = pdf.l_margin + (pdf.epw - display_w) / 2
    pdf.ln(2)
    try:
        pdf.image(str(img_path), x=x_center, w=display_w, h=display_h)
    except Exception as e:
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.multi_cell(0, 5, text=f"[图片加载失败: {img_path.name} - {str(e)[:50]}]", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


def _collect_images(md_file_path: Path | None) -> list[Path]:
    images: list[Path] = []
    search_dirs: list[Path] = []
    seen: set[Path] = set()

    if md_file_path is not None:
        search_dirs.append(md_file_path.parent)
        search_dirs.append(md_file_path.parent / "images")
        search_dirs.append(md_file_path.parent / "image")
        search_dirs.append(md_file_path.parent / "figures")
        search_dirs.append(md_file_path.parent / "img")

    for root in _get_search_roots(md_file_path):
        search_dirs.append(root)
        search_dirs.append(root / "images")
        search_dirs.append(root / "output" / "images")

    img_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    for d in search_dirs:
        try:
            if not d.exists() or not d.is_dir():
                continue
            for f in sorted(d.iterdir(), key=lambda p: p.name):
                if f.is_file() and f.suffix.lower() in img_exts:
                    fp = f.resolve()
                    if fp not in seen:
                        seen.add(fp)
                        images.append(fp)
        except OSError:
            continue

    return images


def _write_markdown(pdf: PDF, md_text: str, font_family: str, md_file_path: Path | None = None):
    lines = md_text.replace("\r\n", "\n").split("\n")
    i = 0
    in_code_block = False
    code_buffer = []
    placeholder_images = _collect_images(md_file_path)
    img_placeholder_idx = 0

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            if in_code_block:
                pdf.ln(2)
                pdf.set_font(font_family, "", 9)
                pdf.set_fill_color(245, 245, 245)
                code_text = "\n".join(code_buffer)
                pdf.multi_cell(0, 5, text=code_text, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)
                pdf.set_text_color(0, 0, 0)
                in_code_block = False
                code_buffer = []
            else:
                in_code_block = True
                code_buffer = []
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        stripped = line.strip()

        if not stripped:
            pdf.ln(2)
            i += 1
            continue

        img_match = re.match(r'!\[(.*?)\]\(([^)]+)\)', stripped)
        if img_match:
            alt_text = img_match.group(1)
            img_ref = img_match.group(2).strip()
            img_ref = img_ref.split(" ")[0]
            img_path = _resolve_asset_path(img_ref, md_file_path)
            if img_path:
                _add_image(pdf, img_path, font_family)
            else:
                pdf.set_font(font_family, "", 10)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 6, text=f"[图片: {alt_text or img_ref}]", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        img_placeholder_match = re.match(r'<!--\s*image\s*-->', stripped, re.IGNORECASE)
        if img_placeholder_match:
            if img_placeholder_idx < len(placeholder_images):
                _add_image(pdf, placeholder_images[img_placeholder_idx], font_family)
                img_placeholder_idx += 1
            else:
                pdf.set_font(font_family, "", 9)
                pdf.set_text_color(150, 150, 150)
                pdf.multi_cell(0, 5, text="[图片占位符: 未找到对应图片文件]", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            sizes = {1: 18, 2: 15, 3: 13, 4: 12, 5: 11, 6: 11}
            spacing = {1: 8, 2: 6, 3: 4, 4: 3, 5: 2, 6: 2}
            pdf.ln(spacing.get(level, 2))
            pdf.set_font(font_family, "B", sizes.get(level, 11))
            pdf.multi_cell(0, sizes.get(level, 11) * 0.6, text=text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue

        table_lines = []
        j = i
        while j < len(lines) and "|" in lines[j]:
            table_lines.append(lines[j])
            j += 1
        if len(table_lines) >= 2 and re.match(r'^\s*\|?[\s\-:|]+\|?\s*$', table_lines[1]):
            headers = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
            rows = []
            for tl in table_lines[2:]:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                while len(cells) < len(headers):
                    cells.append("")
                rows.append(cells[:len(headers)])
            if headers and any(h for h in headers):
                _render_table(pdf, headers, rows, font_family)
                i = j
                continue

        if re.match(r'^\s*[-*+]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*+]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*+]\s+', '', lines[i]).strip()
                items.append(item_text)
                i += 1
            for item in items:
                pdf.set_font(font_family, "", 11)
                pdf.cell(6, 7, text="•")
                x_after_bullet = pdf.get_x()
                remaining_w = pdf.w - pdf.r_margin - x_after_bullet
                pdf.multi_cell(remaining_w, 7, text=_clean_inline(item), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue

        if re.match(r'^\s*\d+\.\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i]).strip()
                items.append(item_text)
                i += 1
            for idx, item in enumerate(items, 1):
                pdf.set_font(font_family, "", 11)
                pdf.cell(8, 7, text=f"{idx}.")
                x_after_num = pdf.get_x()
                remaining_w = pdf.w - pdf.r_margin - x_after_num
                pdf.multi_cell(remaining_w, 7, text=_clean_inline(item), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            quote_text = "\n".join(quote_lines)
            pdf.ln(2)
            pdf.set_font(font_family, "", 10)
            pdf.set_text_color(80, 80, 80)
            x_left = pdf.get_x()
            y_before = pdf.get_y()
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.5)
            pdf.line(x_left + 1, y_before + 1, x_left + 1, y_before + 1)
            pdf.multi_cell(0, 6, text=_clean_inline(quote_text), new_x="LMARGIN", new_y="NEXT")
            y_after = pdf.get_y()
            pdf.set_draw_color(180, 180, 180)
            pdf.line(x_left + 1, y_before, x_left + 1, y_after)
            pdf.set_x(x_left + 5)
            pdf.ln(3)
            pdf.set_text_color(0, 0, 0)
            continue

        if re.match(r'^---+\s*$|^\*\*\*+\s*$|^___+\s*$', stripped):
            pdf.ln(3)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)
            i += 1
            continue

        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            nxt_stripped = nxt.strip()
            if not nxt_stripped:
                break
            if nxt_stripped.startswith(("#", "```", ">", "---", "***", "___", "-", "*", "+", "![")):
                break
            if re.match(r'^\s*\d+\.\s+', nxt):
                break
            if "|" in nxt and i + 1 < len(lines) and re.match(r'^\s*\|?[\s\-:|]+\|?\s*$', lines[i + 1]):
                break
            para_lines.append(nxt_stripped)
            i += 1
        para_text = " ".join(para_lines)
        pdf.set_font(font_family, "", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 7, text=_clean_inline(para_text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)


def _clean_inline(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(([^)]+)\)', r'\1', text)
    return text


def _render_table(pdf, headers, rows, font_family: str):
    col_count = len(headers)
    if col_count == 0:
        return
    col_width = pdf.epw / col_count
    pdf.ln(3)

    pdf.set_font(font_family, "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for h in headers:
        pdf.cell(col_width, 8, text=str(h), border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(font_family, "", 10)
    pdf.set_fill_color(255, 255, 255)
    for row in rows:
        max_lines = 1
        cell_texts = []
        for c_idx in range(col_count):
            val = str(row[c_idx]) if c_idx < len(row) else ""
            cell_texts.append(val)
            lines_needed = max(1, pdf.multi_cell(col_width, 7, text=val, border=0, split_only=True).__len__() if hasattr(pdf, 'multi_cell') else 1)
            line_count = _count_lines(pdf, val, col_width, font_family, "", 10, 7)
            max_lines = max(max_lines, line_count)
        row_h = max(7, 7 * max_lines)
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        for c_idx, val in enumerate(cell_texts):
            x = x_start + c_idx * col_width
            pdf.set_xy(x, y_start)
            pdf.rect(x, y_start, col_width, row_h)
            pdf.set_xy(x + 1, y_start + 1)
            pdf.multi_cell(col_width - 2, 7, text=val, new_x="LMARGIN", new_y="NEXT")
        pdf.set_xy(x_start, y_start + row_h)
    pdf.ln(3)


def _count_lines(pdf, text: str, col_width: float, font_family: str, style: str, size: int, line_h: float) -> int:
    pdf.set_font(font_family, style, size)
    try:
        result = pdf.multi_cell(col_width - 2, line_h, text=text, split_only=True)
        return len(result)
    except Exception:
        return max(1, len(text) // int(col_width / (size * 0.4)) + 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new PDF document (pdf-generator skill).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", required=True, help="Output .pdf path (workspace-relative, e.g. output/r.pdf).")
    parser.add_argument("--title", default=None, help="Document title (shown in header and as Heading 1).")
    parser.add_argument("--author", default=None, help="Document author metadata.")
    parser.add_argument(
        "--headings", default=None, help='JSON array of {"level":1,"text":"..."} (level 1-6).'
    )
    parser.add_argument("--paragraphs", default=None, help="JSON array of body paragraph strings.")
    parser.add_argument("--bullets", default=None, help="JSON array of bullet item strings.")
    parser.add_argument(
        "--table", default=None, help='JSON object {"headers":[...],"rows":[[...],...]} for one table.'
    )
    parser.add_argument(
        "--blocks",
        default=None,
        help=(
            'JSON array of content blocks written IN ORDER: '
            '[{"type":"heading","level":1,"text":"..."},'
            '{"type":"paragraph","text":"..."},'
            '{"type":"bullet","text":"..."},'
            '{"type":"table","headers":[...],"rows":[[...]]},'
            '{"type":"image","path":"images/chart.png"}].'
        ),
    )
    parser.add_argument("--html", default=None, help="HTML content string to render as PDF (basic HTML support).")
    parser.add_argument("--html-file", default=None, help="Path to HTML file to render as PDF.")
    parser.add_argument("--markdown", default=None, help="Markdown content string to render as PDF (supports images).")
    parser.add_argument("--md-file", default=None, help="Path to Markdown (.md) file to render as PDF (supports images).")
    parser.add_argument("--workspace", default=None, help="Workspace root directory for resolving relative paths.")
    parser.add_argument(
        "--page-size", default="A4", choices=["A4", "Letter", "Legal"], help="Page size (default: A4)."
    )
    args = parser.parse_args()

    global _WORKSPACE_ROOT
    if args.workspace:
        _WORKSPACE_ROOT = Path(args.workspace).resolve()

    out_path = _resolve_out_path(args.out)

    page_sizes = {"A4": (210, 297), "Letter": (215.9, 279.4), "Legal": (215.9, 355.6)}
    pdf = PDF(orientation="P", unit="mm", format=page_sizes.get(args.page_size, "A4"))
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf._document_title = args.title or ""

    font_family = _register_font(pdf)
    pdf.add_page()

    if args.author:
        pdf.set_author(args.author)
    if args.title:
        pdf.set_title(args.title)

    n_headings = 0
    n_paragraphs = 0
    n_bullets = 0
    n_tables = 0
    n_images = 0
    n_blocks = 0

    md_file_path = None
    content_mode = None
    content_text = None

    if args.md_file or args.markdown:
        content_mode = "markdown"
        if args.md_file:
            md_path = _resolve_out_path(args.md_file)
            if not md_path.exists():
                print(f"ERROR: Markdown file not found: {md_path}", file=sys.stderr)
                return 2
            md_file_path = md_path
            content_text = md_path.read_text(encoding="utf-8", errors="replace")
        if args.markdown:
            content_text = args.markdown
    elif args.html or args.html_file:
        content_mode = "html"
        if args.html_file:
            html_path = _resolve_out_path(args.html_file)
            if not html_path.exists():
                print(f"ERROR: HTML file not found: {html_path}", file=sys.stderr)
                return 2
            content_text = html_path.read_text(encoding="utf-8", errors="replace")
        if args.html:
            content_text = args.html
    elif args.blocks:
        content_mode = "blocks"

    if content_mode == "markdown":
        if args.title:
            pdf.set_font(font_family, "B", 20)
            pdf.multi_cell(0, 12, text=args.title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
        _write_markdown(pdf, content_text, font_family, md_file_path)
    elif content_mode == "html":
        pdf.set_font(font_family, "", 12)
        pdf.write_html(content_text)
    elif content_mode == "blocks":
        blocks = _parse_json_arg(args.blocks, "--blocks", expect_list=True)
        if blocks is None:
            return 2
        if args.title:
            pdf.set_font(font_family, "B", 20)
            pdf.cell(0, 15, text=args.title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
        for block in blocks:
            added = _add_block(pdf, block, "--blocks", font_family, md_file_path)
            if added is None:
                return 2
            btype = added[0]
            count = added[1]
            n_blocks += 1
            if btype == "heading":
                n_headings += count
            elif btype == "paragraph":
                n_paragraphs += count
            elif btype == "bullet":
                n_bullets += count
            elif btype == "table":
                n_tables += count
            elif btype == "image":
                n_images += count
    else:
        if args.title:
            pdf.set_font(font_family, "B", 20)
            pdf.cell(0, 15, text=args.title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
        if args.headings:
            headings = _parse_json_arg(args.headings, "--headings", expect_list=True)
            if headings is None:
                return 2
            for h in headings:
                _add_heading(pdf, h, font_family)
                n_headings += 1
        if args.paragraphs:
            paras = _parse_json_arg(args.paragraphs, "--paragraphs", expect_list=True)
            if paras is None:
                return 2
            for p in paras:
                _add_paragraph(pdf, str(p), font_family)
                n_paragraphs += 1
        if args.bullets:
            bullets = _parse_json_arg(args.bullets, "--bullets", expect_list=True)
            if bullets is None:
                return 2
            for b in bullets:
                _add_bullet(pdf, str(b), font_family)
                n_bullets += 1
        if args.table:
            tbl = _parse_json_arg(args.table, "--table", expect_list=False)
            if tbl is None:
                return 2
            if _add_table_simple(pdf, tbl, font_family):
                n_tables += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))

    file_size = out_path.stat().st_size
    print(f"OK created: {out_path}")
    print(f"  pages: {pdf.pages_count}")
    print(f"  size: {file_size:,} bytes")
    print(f"  mode: {content_mode or 'simple'}")
    if content_mode != "markdown" and content_mode != "html":
        print(f"  headings: {n_headings}")
        print(f"  paragraphs: {n_paragraphs}")
        print(f"  bullets: {n_bullets}")
        print(f"  tables: {n_tables}")
        print(f"  images: {n_images}")
    if font_family == "Helvetica":
        print("  note: using Helvetica font (Chinese characters may not render; install system CJK font for full support)")
    return 0


def _parse_json_arg(raw: str, name: str, expect_list: bool):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: {name} is not valid JSON: {e}", file=sys.stderr)
        return None
    if expect_list and not isinstance(value, list):
        print(f"ERROR: {name} must be a JSON array.", file=sys.stderr)
        return None
    return value


def _add_block(pdf, block, arg_name: str, font_family: str, md_file_path: Path | None = None):
    if not isinstance(block, dict):
        print(
            f"ERROR: {arg_name} entries must be JSON objects, got {type(block).__name__}.",
            file=sys.stderr,
        )
        return None
    btype = block.get("type")
    if btype == "heading":
        return ("heading", _add_heading(pdf, block, font_family))
    if btype == "paragraph":
        _add_paragraph(pdf, str(block.get("text", "")), font_family)
        return ("paragraph", 1)
    if btype == "bullet":
        _add_bullet(pdf, str(block.get("text", "")), font_family)
        return ("bullet", 1)
    if btype == "table":
        if _add_table_simple(pdf, block, font_family):
            return ("table", 1)
        return None
    if btype == "image":
        img_ref = block.get("path", "")
        img_path = _resolve_asset_path(img_ref, md_file_path)
        if img_path:
            _add_image(pdf, img_path, font_family)
            return ("image", 1)
        else:
            print(f"WARNING: image not found: {img_ref}", file=sys.stderr)
            return None
    print(
        f"ERROR: {arg_name} block has unknown type {btype!r} "
        "(expected heading/paragraph/bullet/table/image).",
        file=sys.stderr,
    )
    return None


def _add_heading(pdf, h: dict, font_family: str) -> int:
    level = max(1, min(6, int(h.get("level", 1))))
    text = str(h.get("text", ""))
    sizes = {1: 18, 2: 15, 3: 13, 4: 12, 5: 11, 6: 11}
    spacing = {1: 8, 2: 6, 3: 4, 4: 3, 5: 2, 6: 2}
    pdf.ln(spacing.get(level, 2))
    pdf.set_font(font_family, "B", sizes.get(level, 11))
    pdf.multi_cell(0, sizes.get(level, 11) * 0.6, text=text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    return 1


def _add_paragraph(pdf, text: str, font_family: str):
    pdf.set_font(font_family, "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, text=text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _add_bullet(pdf, text: str, font_family: str):
    pdf.set_font(font_family, "", 11)
    pdf.cell(8, 7, text="•")
    pdf.multi_cell(0, 7, text=text, new_x="LMARGIN", new_y="NEXT")


def _add_table_simple(pdf, spec, font_family: str) -> bool:
    if not isinstance(spec, dict) or "headers" not in spec:
        print('ERROR: table spec must be {"headers":[...],"rows":[[...]]}.', file=sys.stderr)
        return False
    headers = [str(x) for x in spec.get("headers", [])]
    rows = spec.get("rows", [])
    if not headers:
        return False
    col_width = 190 / len(headers)
    pdf.ln(3)
    pdf.set_font(font_family, "B", 11)
    pdf.set_fill_color(230, 230, 230)
    for h in headers:
        pdf.cell(col_width, 8, text=h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font(font_family, "", 10)
    pdf.set_fill_color(255, 255, 255)
    for row in rows:
        for c_idx in range(len(headers)):
            val = str(row[c_idx]) if c_idx < len(row) else ""
            pdf.cell(col_width, 7, text=val, border=1)
        pdf.ln()
    pdf.ln(3)
    return True


def _resolve_out_path(out_arg: str) -> Path:
    p = Path(out_arg)
    if p.is_absolute():
        return p
    out_clean = out_arg.replace("/", "\\")
    is_root_style = out_clean.startswith("\\")
    if is_root_style:
        out_clean = out_clean.lstrip("\\")
    p = Path(out_clean)

    search_roots = _get_search_roots()
    candidates = []
    for root in search_roots:
        if is_root_style:
            candidates.append(root / p)
            candidates.append(root / "workspace" / p)
            candidates.append(root / "output" / p)
        else:
            candidates.append(root / p)
            candidates.append(root / "workspace" / p)
    candidates.append(p)

    existing = []
    for c in candidates:
        try:
            c_resolved = c.resolve()
            if c.exists():
                existing.append(c_resolved)
        except OSError:
            continue

    if existing:
        return existing[0]

    for c in candidates:
        try:
            if c.parent.exists():
                return c.resolve() if c.parent.exists() else c
        except OSError:
            continue

    return candidates[0] if candidates else p


if __name__ == "__main__":
    raise SystemExit(main())
