from langchain_core.tools import tool
import httpx
import ipaddress
import logging
import os
import re
import socket
from datetime import datetime
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


def _fetch_webpage(url: str, max_content_chars: int = _MAX_CONTENT_CHARS) -> str:
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
            md = md[:max_content_chars] + "\n\n[...内容过长已截断...]"
        return md[:max_content_chars]
    except Exception as e:
        # 抓取失败不阻断流程，调用方降级为只用 snippet；记录原因便于排查
        logger.warning("Fetch webpage failed: %s -> %s: %s", url, type(e).__name__, e)
        return ""


def _extract_key_info(content: str) -> str:
    """从正文中提取关键信息：前3句 + 含数字的句子（最多5句），供 LLM 了解正文概要。

    不替代完整正文——完整正文已通过 save_to 直接写入文件。
    """
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if not lines:
        return ""

    key_lines: list[str] = []
    # 前3个非空行（通常是文章开头的概述）
    for line in lines[:3]:
        if len(line) > 10:
            key_lines.append(line)
    # 含数字/百分比的句子（数据点）
    num_pattern = re.compile(r"\d+[.,]?\d*\s*[%亿万千百]?|CAGR|\$|增长率|市场|规模", re.IGNORECASE)
    for line in lines:
        if len(key_lines) >= 8:
            break
        if line not in key_lines and num_pattern.search(line) and len(line) > 15:
            key_lines.append(line)

    return "\n".join(f"  - {l}" for l in key_lines[:8])


def _append_research_to_file(
    filepath: str, query: str, provider: str, results: list, topic: str,
    fetch_top_n: int, max_content_chars: int, phase: str = "",
) -> None:
    """把完整搜索结果（含全文正文）追加写入研究素材文件。不经 LLM，保证原始内容不丢失。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"\n\n{'='*60}\n## 搜索记录 | {timestamp}\n- **关键词**: {query}\n- **来源**: {provider}\n- **类型**: {topic}\n- **阶段**: {phase or '未标注'}\n- **结果数**: {len(results)}\n{'='*60}\n"

    parts = [header]
    for idx, r in enumerate(results):
        entry = f"\n### [{idx+1}] {r.title or '（无标题）'}\n**URL**: {r.url or '（无链接）'}\n**摘要**: {r.snippet or '（无摘要）'}\n"
        # 对前 N 个结果抓取完整正文
        if idx < fetch_top_n and r.url:
            content = _fetch_webpage(r.url, max_content_chars) if _is_safe_target_url(r.url) else ""
            if content:
                entry += f"\n**正文（{len(content)}字）**:\n\n{content}\n"
            else:
                entry += "\n**正文**: 抓取失败\n"
        parts.append(entry)

    content_to_write = "\n".join(parts)

    # 确保目录存在
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    # 追加写入
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content_to_write)


@tool
def web_search(query: str, max_results: int = 5, topic: str = "general",
               fetch_top_n: int = _FETCH_TOP_N, max_content_chars: int = _MAX_CONTENT_CHARS,
               save_to: str = "", phase: str = "") -> str:
    """搜索网络，返回标题+链接+摘要+关键信息，并可自动把完整结果（含全文正文）保存到文件。

    搜索源按 failover 顺序尝试:Tavily → Brave → Serper → DuckDuckGo。
    某个 provider 额度耗尽(HTTP 429/402)时自动冷却 1 小时并切换到下一个,
    三个第三方全部不可用时回退到 DuckDuckGo。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认5
        topic: 搜索类型。'general' 通用搜索（默认），'news' 新闻搜索（优先返回近期资讯）
        fetch_top_n: 对前N个结果抓取完整正文（转Markdown），默认2。
                     传0表示不抓正文（广度搜索阶段用），传3+用于深度搜索阶段。
        max_content_chars: 单篇正文截断字符数，默认4000。深度搜索阶段可提高到8000。
        save_to: 若指定文件路径，完整搜索结果（含全文正文）将直接追加写入该文件（不经LLM压缩），
                 返回给LLM的是精简版（标题+链接+摘要+关键信息提取）。
                 用于研究素材收集——确保原始内容100%保留到文件供后续阶段读取。
        phase: 搜索阶段标注（如"广度"/"深度"），写入文件时记录，便于追溯。
    """
    import asyncio

    from tools.search import get_search_results, SearchQuery

    async def _run() -> str:
        sq = SearchQuery(query=query, max_results=max_results, topic=topic)
        results, provider_name = await get_search_results(sq)
        if not results:
            return "没有找到相关结果"

        # 如果指定了 save_to，完整结果（含全文正文）直接追加写入文件
        if save_to:
            _append_research_to_file(
                save_to, query, provider_name, results, topic,
                fetch_top_n, max_content_chars, phase,
            )

        # 返回给 LLM 的是精简版（避免上下文爆炸）
        # 如果有 save_to，正文部分只返回关键信息提取；如果没有 save_to，返回完整正文（向后兼容）
        parts = [f"[搜索来源: {provider_name}]"]
        if save_to:
            parts.append(f"[完整结果已保存到: {save_to}]")
        for idx, r in enumerate(results):
            # 基础条目：标题 + 链接 + 摘要
            entry = f"[{idx+1}] [{r.title or '（无标题）'}]({r.url or '（无链接）'})\n{r.snippet or '（无摘要）'}"

            if idx < fetch_top_n and r.url:
                content = _fetch_webpage(r.url, max_content_chars) if _is_safe_target_url(r.url) else ""
                if content:
                    if save_to:
                        # save_to 模式：只返回关键信息提取（完整正文已在文件里）
                        key_info = _extract_key_info(content)
                        entry += f"\n  正文关键信息（{len(content)}字，完整版见文件）:\n{key_info}"
                    else:
                        # 无 save_to：返回完整正文（向后兼容）
                        entry += f"\n\n## 正文\n{content}"

            parts.append(entry)

        return "\n\n---\n\n".join(parts)

    # web_search 是同步 @tool,LangChain astream 会在独立线程中调用它,
    # 当前线程没有运行中的事件循环,可直接 asyncio.run()。
    try:
        return asyncio.run(_run())
    except Exception as e:
        return f"搜索时出错：{str(e)}"
