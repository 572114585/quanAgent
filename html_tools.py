"""HTML 渲染工具。

把 HTML 文件用无头 Chromium 渲染成 PNG 截图。为什么需要这个工具：
web-design-engineer 等 skill 产出的 HTML 含 React/Chart.js/D3/oklch 等
需浏览器执行的前端技术，但在微信等渠道里无法直接打开 HTML。这个工具把
HTML 截图成 PNG，让用户在无法渲染 HTML 的渠道里也能看到设计效果。

风格对齐 ducktools.py / time_tools.py：
- @tool 装饰，函数名即工具名，docstring 即 LLM 可见的工具描述
- try/except 全捕获，错误返回中文 str（不 raise），对 LLM 友好
"""
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
) -> str:
    """把 HTML 文件渲染成 PNG 截图。当产物含 React/Chart.js/D3/oklch 等
    需浏览器渲染的现代前端，或要在微信等无法打开 HTML 的渠道里展示网页设计效果时调用。

    参数：
    - html_path: 要渲染的 HTML 文件路径（支持 output/xxx.html、/output/xxx.html、绝对路径）
    - output_path: PNG 输出路径，留空则输出到 HTML 同目录同名 .png（推荐留空）
    - full_page: 是否截整页（滚动到底部），默认 True；PPT/固定尺寸场景传 False
    - width/height: 视口尺寸，默认 1440x900；PPT 用 1920x1080，手机原型用 390x844
    - wait_ms: networkidle 之后的额外等待毫秒，默认 1500（兜底异步渲染）

    返回渲染结果或错误信息（中文）。
    """
    try:
        html_abs = _resolve_html_path(html_path)
        if html_abs is None:
            return f"渲染失败：找不到 HTML 文件 {html_path}。请确认路径正确（如 output/xxx.html），且文件已生成。"

        out_abs = Path(output_path) if output_path else _default_output_path(html_abs)
        if not out_abs.is_absolute() and "workspace" not in out_abs.parts:
            # 相对路径且没带 workspace 前缀 → 相对 workspace 根补全。
            # 与 _resolve_html_path 的 workspace 根约定一致。
            out_abs = Path("workspace") / out_abs
        # 保证输出目录存在（output/ 已由 agent_runtime 创建，但 tmp/ 或自定义路径可能没有）
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        # 延迟 import：避免 agent 进程未装 playwright 时启动即崩。
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_default_timeout(_PAGE_TIMEOUT_MS)
                # file:// 加载本地 HTML，相对资源路径才能正确解析。
                # wait_until="networkidle" 等 CDN（React/Chart.js/Google Fonts）加载完，
                # 但 React 渲染是 JS 执行，networkidle 不一定等得到，所以再补固定延时。
                page.goto(_file_url(html_abs), wait_until="networkidle")
                page.wait_for_timeout(wait_ms)
                page.screenshot(path=str(out_abs), full_page=full_page)
            finally:
                browser.close()

        # 读取实际截图尺寸用于反馈
        size_str = ""
        try:
            from PIL import Image
            with Image.open(out_abs) as img:
                size_str = f"，尺寸 {img.width}x{img.height}"
        except Exception:
            pass

        # 返回相对 workspace 的路径，便于 LLM 在 output/ 约定下汇报。
        try:
            rel = out_abs.resolve().relative_to(Path("workspace").resolve())
            out_display = str(rel).replace("\\", "/")
        except (ValueError, OSError):
            out_display = str(out_abs)

        return f"已渲染：{out_display}{size_str}。PNG 用于即时预览，HTML 源文件供用户下载到浏览器交互。"
    except Exception as e:
        return f"渲染失败：{type(e).__name__}: {e}"
