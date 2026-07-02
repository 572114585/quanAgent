"""
Playwright HTML 转 PDF 测试脚本
测试目标:验证 HTML 中包含在线图片链接时,能否成功渲染到 PDF
"""
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# 输出目录
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
PDF_PATH = OUTPUT_DIR / "playwright_test.pdf"

# 测试用 HTML:包含多张在线图片(使用 picsum.photos 公共图床)
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Playwright HTML 转 PDF 测试</title>
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 40px; color: #222; }
  h1 { color: #1a365d; border-bottom: 3px solid #2b6cb0; padding-bottom: 8px; }
  h2 { color: #2b6cb0; margin-top: 32px; }
  .img-block { margin: 20px 0; text-align: center; }
  .img-block img { max-width: 80%; border: 1px solid #ddd; border-radius: 4px; }
  .caption { color: #666; font-size: 13px; margin-top: 6px; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
  th { background: #edf2f7; font-weight: 600; }
  .badge { display: inline-block; padding: 2px 8px; background: #c6f6d5; color: #22543d; border-radius: 4px; font-size: 12px; }
</style>
</head>
<body>
  <h1>Playwright HTML 转 PDF 测试报告</h1>
  <p>本测试用于验证:当 HTML 中通过 <code>&lt;img src="https://..."&gt;</code> 引用在线图片时,
  Playwright 能否在生成的 PDF 中正确渲染这些图片。</p>

  <h2>1. 在线图片渲染测试</h2>
  <div class="img-block">
    <img src="https://picsum.photos/id/1015/800/400" alt="山景图">
    <div class="caption">图 1:在线图片(picsum.photos/id/1015)</div>
  </div>

  <div class="img-block">
    <img src="https://picsum.photos/id/1025/800/300" alt="小狗图">
    <div class="caption">图 2:在线图片(picsum.photos/id/1025)</div>
  </div>

  <h2>2. 多元素混合渲染测试</h2>
  <p>除了图片,还要验证表格、徽章等元素的渲染效果。</p>

  <table>
    <thead>
      <tr><th>项目</th><th>结果</th><th>说明</th></tr>
    </thead>
    <tbody>
      <tr><td>中文字体</td><td><span class="badge">通过</span></td><td>微软雅黑正常渲染</td></tr>
      <tr><td>在线图片</td><td><span class="badge">通过</span></td><td>等待 networkidle 后渲染</td></tr>
      <tr><td>表格样式</td><td><span class="badge">通过</span></td><td>边框、背景色生效</td></tr>
    </tbody>
  </table>

  <h2>3. 结论</h2>
  <p>如果上方两张图片均可见,说明 Playwright 可以完整渲染带在线图片链接的 HTML 到 PDF。</p>
</body>
</html>
"""


async def html_to_pdf(html: str, pdf_path: Path) -> dict:
    """将 HTML 字符串转为 PDF,返回渲染统计信息"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        # 设置 HTML 内容
        await page.set_content(html, wait_until="networkidle")

        # 额外等待,确保图片完全解码
        await page.wait_for_timeout(1000)

        # 统计页面上的图片数量
        img_count = await page.evaluate("document.images.length")
        # 检查每张图片是否已加载(naturalWidth > 0 表示加载成功)
        loaded = await page.evaluate(
            """() => Array.from(document.images).map(img => ({
                src: img.src,
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
                complete: img.complete
            }))"""
        )

        # 生成 PDF
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
        )

        await browser.close()

        return {
            "img_count": img_count,
            "images": loaded,
            "pdf_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
        }


async def main():
    print("=" * 60)
    print("Playwright HTML 转 PDF 测试")
    print("=" * 60)
    print(f"输出路径: {PDF_PATH}")
    print()

    result = await html_to_pdf(HTML_CONTENT, PDF_PATH)

    print(f"[1] 页面图片数量: {result['img_count']}")
    for i, img in enumerate(result["images"], 1):
        status = "✓ 加载成功" if img["naturalWidth"] > 0 else "✗ 加载失败"
        print(f"    图片 {i}: {status}")
        print(f"      src: {img['src']}")
        print(f"      尺寸: {img['naturalWidth']}x{img['naturalHeight']}, complete={img['complete']}")

    print()
    print(f"[2] PDF 文件大小: {result['pdf_size']} 字节 "
          f"({result['pdf_size'] / 1024:.1f} KB)")

    if result["pdf_size"] > 0:
        print()
        print("=" * 60)
        print(f"测试完成!PDF 已生成: {PDF_PATH}")
        print("=" * 60)
        return 0
    else:
        print("PDF 生成失败!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
