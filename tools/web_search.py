from langchain_core.tools import tool
import httpx
import ipaddress
import logging
import socket
from urllib.parse import urlparse
from markdownify import markdownify

logger = logging.getLogger(__name__)

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
# 单篇正文最大下载字节数，防止恶意大文件拖垮 agent
_MAX_FETCH_BYTES = 512 * 1024  # 512KB


def _is_safe_target_url(url: str) -> bool:
    """检查 URL 是否可安全抓取：仅 http(s)，拒绝内网/回环/链路本地地址，防 SSRF。

    对重定向目标同样适用：httpx follow_redirects=True 时，最终响应 URL 也需在
    _fetch_webpage 中再次校验。
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if not hostname:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            return False
    return True


def _fetch_webpage(url: str) -> str:
    """抓取网页正文并转为 Markdown。失败时返回空字符串（降级为只给 snippet）。"""
    if not _is_safe_target_url(url):
        logger.warning("Refused to fetch unsafe URL (private/loopback): %s", url)
        return ""
    try:
        # 用流式读取限制最大字节数，防止恶意大文件耗尽内存
        chunks: list[bytes] = []
        total = 0
        too_large = False
        text = ""
        with httpx.stream(
            "GET",
            url,
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        ) as resp:
            # 校验重定向后的最终 URL，防 30x 跳到内网
            final_url = str(resp.url)
            if final_url != url and not _is_safe_target_url(final_url):
                logger.warning("Refused redirected unsafe URL: %s -> %s", url, final_url)
                return ""
            resp.raise_for_status()
            encoding = resp.encoding or "utf-8"
            for chunk in resp.iter_bytes(chunk_size=8192):
                total += len(chunk)
                if total > _MAX_FETCH_BYTES:
                    too_large = True
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            text = raw.decode(encoding, errors="replace")
        md = markdownify(text)
        if too_large:
            md = md[:_MAX_CONTENT_CHARS] + "\n\n[...内容过长已截断...]"
        return md[:_MAX_CONTENT_CHARS]
    except Exception as e:
        # 抓取失败不阻断流程，调用方降级为只用 snippet；记录原因便于排查
        logger.warning("Fetch webpage failed: %s -> %s: %s", url, type(e).__name__, e)
        return ""


@tool
def web_search(query: str, max_results: int = 5, topic: str = "general") -> str:
    """搜索网络，返回标题+链接+摘要，并对前2个结果抓取完整正文（转Markdown）。

    搜索源按 failover 顺序尝试:Tavily → Brave → Serper → DuckDuckGo。
    某个 provider 额度耗尽(HTTP 429/402)时自动冷却 1 小时并切换到下一个,
    三个第三方全部不可用时回退到 DuckDuckGo。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认5
        topic: 搜索类型。'general' 通用搜索（默认），'news' 新闻搜索（优先返回近期资讯）
    """
    import asyncio

    from tools.search import get_search_results, SearchQuery

    async def _run() -> str:
        sq = SearchQuery(query=query, max_results=max_results, topic=topic)
        results, provider_name = await get_search_results(sq)
        if not results:
            return "没有找到相关结果"

        parts = [f"[搜索来源: {provider_name}]"]
        for idx, r in enumerate(results):
            # 基础条目：标题 + 链接 + 摘要
            entry = f"[{r.title or '（无标题）'}]({r.url or '（无链接）'})\n{r.snippet or '（无摘要）'}"

            # 对前 N 个结果抓取正文，补充深度内容
            if idx < _FETCH_TOP_N and r.url:
                content = _fetch_webpage(r.url) if _is_safe_target_url(r.url) else ""
                if content:
                    entry += f"\n\n## 正文\n{content}"

            parts.append(entry)

        return "\n\n---\n\n".join(parts)

    # web_search 是同步 @tool,LangChain astream 会在独立线程中调用它,
    # 当前线程没有运行中的事件循环,可直接 asyncio.run()。
    try:
        return asyncio.run(_run())
    except Exception as e:
        return f"搜索时出错：{str(e)}"
