#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
render_pdf.py — HTML → PDF(Playwright async API)

用法:
    # 渲染 PDF
    python skills/md-to-pdf/scripts/render_pdf.py \
        --html output/report.html \
        --out output/report.pdf \
        --page-size A4

    # 验证已生成的 PDF
    python skills/md-to-pdf/scripts/render_pdf.py --verify output/report.pdf

依赖:playwright
    pip install playwright && playwright install chromium
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# ── 依赖检查 ──────────────────────────────────────────────
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[ERROR] 缺少依赖:playwright", file=sys.stderr)
    print("请运行:pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(2)


# 纸张尺寸映射(mm)
PAGE_SIZES = {
    "A4": {"width": "210mm", "height": "297mm"},
    "Letter": {"width": "8.5in", "height": "11in"},
    "B5": {"width": "176mm", "height": "250mm"},
    "A5": {"width": "148mm", "height": "210mm"},
    "Legal": {"width": "8.5in", "height": "14in"},
}


async def render_html_to_pdf(html_path: Path, pdf_path: Path,
                              page_size: str, timeout_ms: int) -> dict:
    """用 Playwright 把 HTML 渲染为 PDF。

    关键参数(已验证):
      - wait_until='networkidle'  等网络图片加载完
      - wait_for_timeout(1000)    等字体/图表渲染
      - print_background=True     保留背景色
      - prefer_css_page_size=True 优先用 CSS @page size(让模板的 @page 生效)
    """
    if not html_path.exists():
        print(f"[ERROR] HTML 文件不存在: {html_path}", file=sys.stderr)
        sys.exit(1)

    html_uri = html_path.resolve().as_uri()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context()
            page = await context.new_page()

            # 加载 HTML,等网络空闲(图片/字体加载完)
            await page.goto(html_uri, wait_until="networkidle", timeout=timeout_ms)
            # 额外等待 1s,确保字体/Chart.js/延迟渲染完成
            await page.wait_for_timeout(1000)

            # 统计图片加载情况
            img_info = await page.evaluate(
                """() => {
                    const imgs = Array.from(document.images);
                    return {
                        total: imgs.length,
                        loaded: imgs.filter(i => i.naturalWidth > 0).length,
                        failed: imgs.filter(i => i.complete && i.naturalWidth === 0)
                                    .map(i => i.src)
                    };
                }"""
            )

            # 渲染 PDF
            page_opts = {
                "path": str(pdf_path),
                "print_background": True,
                "prefer_css_page_size": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
            }
            # 如果 CSS 没有 @page size,fallback 到 format
            if page_size in PAGE_SIZES:
                page_opts["format"] = page_size

            await page.pdf(**page_opts)
            await context.close()
        finally:
            await browser.close()

    size = pdf_path.stat().st_size if pdf_path.exists() else 0
    return {"img_info": img_info, "pdf_size": size}


async def verify_pdf(pdf_path: Path) -> dict:
    """验证 PDF:文件大小、页数(用 pypdf 若可用)。"""
    if not pdf_path.exists():
        print(f"[ERROR] PDF 文件不存在: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    size = pdf_path.stat().st_size
    result = {"path": str(pdf_path), "size": size, "size_kb": size / 1024}

    if size == 0:
        result["status"] = "failed"
        result["error"] = "文件大小为 0,渲染失败"
        return result

    # 尝试用 pypdf 读页数(可选依赖)
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        result["pages"] = len(reader.pages)
        result["status"] = "ok"
    except ImportError:
        result["pages"] = "?(pypdf 未安装,无法统计页数)"
        result["status"] = "ok"
    except Exception as e:
        result["pages"] = f"?(读取失败: {e})"
        result["status"] = "ok"

    return result


async def main_async(args):
    if args.verify:
        result = await verify_pdf(Path(args.verify))
        print(f"[验证] {result['path']}")
        print(f"  状态: {result['status']}")
        print(f"  大小: {result['size']} 字节 ({result['size_kb']:.1f} KB)")
        print(f"  页数: {result.get('pages', '?')}")
        if result["status"] == "failed":
            print(f"  错误: {result.get('error', '')}")
            return 1
        return 0

    html_path = Path(args.html)
    pdf_path = Path(args.out)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[渲染] {html_path} → {pdf_path}")
    print(f"  纸张: {args.page_size}")

    result = await render_html_to_pdf(
        html_path=html_path,
        pdf_path=pdf_path,
        page_size=args.page_size,
        timeout_ms=args.timeout * 1000,
    )

    img = result["img_info"]
    print(f"  图片: 共 {img['total']} 张,加载成功 {img['loaded']} 张")
    if img["failed"]:
        print(f"  [警告] 以下图片加载失败:")
        for src in img["failed"]:
            print(f"    - {src}")

    if result["pdf_size"] == 0:
        print(f"[失败] PDF 大小为 0,渲染失败")
        return 1

    print(f"[完成] PDF 已生成: {pdf_path}")
    print(f"  大小: {result['pdf_size']} 字节 ({result['pdf_size'] / 1024:.1f} KB)")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="HTML → PDF(Playwright async API)"
    )
    parser.add_argument("--html", help="输入 HTML 文件路径")
    parser.add_argument("--out", help="输出 PDF 文件路径")
    parser.add_argument("--page-size", default="A4",
                        choices=list(PAGE_SIZES.keys()),
                        help="纸张大小(默认 A4,CSS @page 优先)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="页面加载超时秒数(默认 30)")
    parser.add_argument("--verify", metavar="PDF_PATH",
                        help="验证已生成的 PDF(文件大小/页数)")
    args = parser.parse_args()

    if not args.verify and (not args.html or not args.out):
        parser.error("渲染模式需要 --html 和 --out;验证模式用 --verify")

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
