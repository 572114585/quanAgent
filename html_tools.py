"""HTML 渲染工具。

把 HTML 文件或 dev server URL 用无头 Chromium 渲染成 PNG 截图。为什么需要这个工具：
web-design-engineer 等 skill 产出的 HTML 含 React/Chart.js/D3/oklch 等
需浏览器执行的前端技术，但在微信等渠道里无法直接打开 HTML。这个工具把
HTML 截图成 PNG，让用户在无法渲染 HTML 的渠道里也能看到设计效果。

也支持对 Vite dev server 等 http://localhost:<port> URL 截图，用于
web-video-presentation 等需要 dev server 运行时才能渲染的项目预览。

风格对齐 ducktools.py / time_tools.py：
- @tool 装饰，函数名即工具名，docstring 即 LLM 可见的工具描述
- try/except 全捕获，错误返回中文 str（不 raise），对 LLM 友好
"""
import re
from pathlib import Path, PurePath
from urllib.parse import quote, urljoin

from langchain_core.tools import tool


# render_html 工具的默认视口宽高，覆盖多数桌面端落地页/仪表盘场景。
# PPT(1920x1080)、手机原型(390x844) 等特殊尺寸由 LLM 传参覆盖。
_DEFAULT_WIDTH = 1440
_DEFAULT_HEIGHT = 900
# networkidle 之后的固定延时，兜底 React/Chart.js 异步渲染。
_DEFAULT_WAIT_MS = 1500
# 截图最大等待总时长，防止异常页面卡死 agent。
_PAGE_TIMEOUT_MS = 30_000


def _resolve_html_path(html_path: str) -> Path | None:
    """把 LLM 传入的各种路径形态规范化为 workspace 根下的绝对路径。

    兼容 agent_runtime 的 path normalization 约定：
    - output/xxx.html        → workspace/output/xxx.html
    - /output/xxx.html       → workspace/output/xxx.html（剥前导 /）
    - D:\\project\\workspace\\output\\xxx.html → 原样
    - 不存在的文件返回 None（让上层报错）
    """
    if not html_path or not isinstance(html_path, str):
        return None
    text = html_path.strip().strip('"').strip("'")
    if not text:
        return None

    # 去掉前导 /（虚拟绝对路径形式），统一成相对路径再相对 workspace 解析。
    # 与 agent_runtime._rewrite_path_token 的「虚拟绝对路径剥前导 /」一致。
    if text.startswith("/"):
        text = text.lstrip("/")

    candidate = Path(text)
    if not candidate.is_absolute():
        # workspace 是 agent 的工作根目录（与 agent_runtime.py 的 root_dir 一致）。
        # 但 LLM 可能传带 workspace/ 前缀的路径，也可能传不带；两种都试，哪个存在用哪个。
        # 不能简单无脑拼 workspace，否则 workspace/tmp/x → workspace/workspace/tmp/x 找不到。
        if candidate.exists():
            return candidate
        prefixed = Path("workspace") / candidate
        if prefixed.exists():
            return prefixed
        return None

    return candidate if candidate.exists() else None


def _default_output_path(html_abs: Path) -> Path:
    """PNG 默认输出到与 HTML 同目录、同文件名（仅换扩展名）。"""
    return html_abs.with_suffix(".png")


def _file_url(p: Path) -> str:
    """把本地路径转成 file:// URL，Windows 路径分隔符与中文都正确转义。"""
    # PurePath.as_posix() 把反斜杠统一成正斜杠，再 file:// 前缀 + URL quote。
    posix = p.resolve().as_posix()
    # quote 保留 / 不编码（safe='/'），编码中文与空格等。
    return "file:///" + quote(posix, safe="/")


@tool
def render_html(
    html_path: str,
    output_path: str = "",
    full_page: bool = True,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    wait_ms: int = _DEFAULT_WAIT_MS,
    steps: list[int] | None = None,
) -> str:
    """把 HTML 文件或 dev server URL 渲染成 PNG 截图。当产物含 React/Chart.js/D3/oklch 等
    需浏览器渲染的现代前端，或要在微信等无法打开 HTML 的渠道里展示网页设计效果时调用。

    也支持对 http://localhost:<port> 的 Vite dev server 截图，配合 steps 参数可模拟
    点击推进到指定步数再截图，用于 web-video-presentation 的章节预览。

    参数：
    - html_path: 要渲染的 HTML 文件路径或 dev server URL。
      文件路径支持 output/xxx.html、/output/xxx.html、绝对路径；
      URL 支持 http://localhost:5173 等 dev server 地址。
    - output_path: PNG 输出路径，留空则自动生成（推荐留空）
    - full_page: 是否截整页（滚动到底部），默认 True；PPT/固定尺寸场景传 False
    - width/height: 视口尺寸，默认 1440x900；PPT 用 1920x1080，手机原型用 390x844
    - wait_ms: networkidle 之后的额外等待毫秒，默认 1500（兜底异步渲染）
    - steps: 步数列表，仅当 html_path 为 dev server URL 时有效。
      传入如 [0, 3, 7] 表示分别推进到第 0/3/7 步时截图，产出多张 PNG。
      每次推进通过点击舞台中央 (width/2, height/2) 模拟。
      输出到 output/preview/step-00.png、step-03.png、step-07.png。
      留空或不传则只截一张当前页面。

    返回渲染结果或错误信息（中文）。
    """
    is_url = isinstance(html_path, str) and html_path.strip().startswith(("http://", "https://"))

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return f"渲染失败：playwright 未安装或不可用: {e}"

    try:
        # --- 确定输出目录 ---
        if is_url and steps:
            # steps 模式：输出到 output/preview/
            out_dir = Path("workspace/output/preview")
            out_dir.mkdir(parents=True, exist_ok=True)
        elif output_path:
            out_abs = Path(output_path)
            if not out_abs.is_absolute() and "workspace" not in out_abs.parts:
                out_abs = Path("workspace") / out_abs
            out_abs.parent.mkdir(parents=True, exist_ok=True)
        # else: out_abs 在下面按分支确定

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_default_timeout(_PAGE_TIMEOUT_MS)

                if is_url:
                    # --- URL 模式 ---
                    page.goto(html_path.strip(), wait_until="networkidle")
                    page.wait_for_timeout(wait_ms)

                    if steps:
                        # steps 模式：推进到指定步数截图
                        max_step = max(steps)
                        captured: list[str] = []
                        for i in range(max_step + 1):
                            if i > 0:
                                # 点击舞台中央推进
                                page.mouse.click(width // 2, height // 2)
                                page.wait_for_timeout(400)
                            if i in steps:
                                out_file = out_dir / f"step-{i:02d}.png"
                                page.screenshot(path=str(out_file), full_page=full_page)
                                try:
                                    rel = out_file.resolve().relative_to(Path("workspace").resolve())
                                    captured.append(str(rel).replace("\\", "/"))
                                except (ValueError, OSError):
                                    captured.append(str(out_file))
                        return f"已渲染 {len(captured)} 张截图（steps={steps}）：\n" + "\n".join(
                            f"  - {c}" for c in captured
                        )
                    else:
                        # 单张 URL 截图
                        if output_path:
                            out_abs = Path(output_path)
                            if not out_abs.is_absolute() and "workspace" not in out_abs.parts:
                                out_abs = Path("workspace") / out_abs
                        else:
                            safe_name = re.sub(r'[^\w]', '_', html_path.strip())[:50]
                            out_abs = Path("workspace/output") / f"url-{safe_name}.png"
                        out_abs.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(out_abs), full_page=full_page)

                else:
                    # --- 文件模式（原有逻辑）---
                    html_abs = _resolve_html_path(html_path)
                    if html_abs is None:
                        return f"渲染失败：找不到 HTML 文件 {html_path}。请确认路径正确（如 output/xxx.html），且文件已生成。"

                    if output_path:
                        out_abs = Path(output_path)
                        if not out_abs.is_absolute() and "workspace" not in out_abs.parts:
                            out_abs = Path("workspace") / out_abs
                    else:
                        out_abs = _default_output_path(html_abs)
                    out_abs.parent.mkdir(parents=True, exist_ok=True)

                    page.goto(_file_url(html_abs), wait_until="networkidle")
                    page.wait_for_timeout(wait_ms)
                    page.screenshot(path=str(out_abs), full_page=full_page)

            finally:
                browser.close()

        # --- 构建返回消息 ---
        if is_url and steps:
            # 已在上面返回
            pass

        # 读取实际截图尺寸
        size_str = ""
        try:
            from PIL import Image
            target = out_abs if 'out_abs' in dir() else None
            if target and target.exists():
                with Image.open(target) as img:
                    size_str = f"，尺寸 {img.width}x{img.height}"
        except Exception:
            pass

        # 返回相对 workspace 的路径
        try:
            if 'out_abs' in dir() and out_abs.exists():
                rel = out_abs.resolve().relative_to(Path("workspace").resolve())
                out_display = str(rel).replace("\\", "/")
            else:
                out_display = str(out_abs) if 'out_abs' in dir() else html_path
        except (ValueError, OSError):
            out_display = str(out_abs) if 'out_abs' in dir() else html_path

        source_desc = f"URL: {html_path}" if is_url else "HTML 源文件供用户下载到浏览器交互"
        return f"已渲染：{out_display}{size_str}。PNG 用于即时预览，{source_desc}。"
    except Exception as e:
        return f"渲染失败：{type(e).__name__}: {e}"
