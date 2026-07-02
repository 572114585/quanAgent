from langchain_core.tools import tool
from ddgs import DDGS
import httpx
from markdownify import markdownify

# 抓正文的用户代理头，避免被部分站点拦截
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# 每篇正文截断长度，防止子 agent 上下文爆炸
_MAX_CONTENT_CHARS = 4000
# 抓取超时（秒）
_FETCH_TIMEOUT = 10.0
# 每次搜索抓几篇正文（取结果里的前 N 个）
_FETCH_TOP_N = 2


def _fetch_webpage(url: str) -> str:
    """抓取网页正文并转为 Markdown。失败时返回空字符串（降级为只给 snippet）。"""
    try:
        resp = httpx.get(
            url,
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
        resp.raise_for_status()
        md = markdownify(resp.text)
        return md[:_MAX_CONTENT_CHARS]
    except Exception:
        # 抓取失败不阻断流程，调用方降级为只用 snippet
        return ""


@tool
def web_search(query: str, max_results: int = 5, topic: str = "general") -> str:
    """搜索网络，返回标题+链接+摘要，并对前2个结果抓取完整正文（转Markdown）。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认5
        topic: 搜索类型。'general' 通用搜索（默认），'news' 新闻搜索（优先返回近期资讯）
    """
    try:
        with DDGS() as ddgs:
            if topic == "news":
                # ddgs.news 返回字段：title/url/body/date 等
                results = list(ddgs.news(query, max_results=max_results))
            else:
                results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "没有找到相关结果"

        parts = []
        for idx, item in enumerate(results):
            title = item.get("title", "（无标题）")
            # news 接口字段叫 url，text 接口叫 href
            href = item.get("url") or item.get("href", "（无链接）")
            body = item.get("body", "（无摘要）")

            # 基础条目：标题 + 链接 + 摘要
            entry = f"[{title}]({href})\n{body}"

            # 对前 N 个结果抓取正文，补充深度内容
            if idx < _FETCH_TOP_N:
                content = _fetch_webpage(href)
                if content:
                    entry += f"\n\n## 正文\n{content}"

            parts.append(entry)

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"搜索时出错：{str(e)}"
