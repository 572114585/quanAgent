"""联网搜索工具：多 Provider fusion，返回标题+链接+摘要（正文抓取见 web_fetch）。"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from datetime import datetime

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_SNIPPET_MAX = 500


def _run_coro(coro):
    """在同步 @tool 内安全跑 async：无 loop 用 asyncio.run；有 loop 则线程内跑。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _append_research_to_file(
    filepath: str,
    query: str,
    provider: str,
    results: list,
    topic: str,
    phase: str = "",
) -> None:
    """把搜索结果（标题+链接+摘要）追加写入研究素材文件。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        f"\n\n{'='*60}\n## 搜索记录 | {timestamp}\n"
        f"- **关键词**: {query}\n"
        f"- **来源**: {provider}\n"
        f"- **类型**: {topic}\n"
        f"- **阶段**: {phase or '未标注'}\n"
        f"- **结果数**: {len(results)}\n"
        f"{'='*60}\n"
    )

    parts = [header]
    for idx, r in enumerate(results):
        src_type = getattr(r, "source_type", "") or ""
        domain = getattr(r, "domain", "") or ""
        published = getattr(r, "published_at", "") or ""
        entry = (
            f"\n### [{idx+1}] {r.title or '（无标题）'}\n"
            f"**URL**: {r.url or '（无链接）'}\n"
            f"**域名**: {domain or '—'}\n"
            f"**类型**: {src_type or '—'}\n"
            f"**发布**: {published or '—'}\n"
            f"**摘要**: {r.snippet or '（无摘要）'}\n"
        )
        parts.append(entry)

    from pathlib import Path

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n".join(parts))


def _web_refs_marker(refs: list[dict]) -> str:
    return f"<!--WEB_REFS:{json.dumps(refs, ensure_ascii=False)}-->"


@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: str = "general",
    save_to: str = "",
    phase: str = "",
    search_depth: str = "basic",
) -> str:
    """搜索网络，返回标题+链接+摘要。正文抓取请用 web_fetch(url)。

    默认并行融合多搜索源(Tavily/Brave/Serper/DuckDuckGo)：去重、域名多样性、权威加权。
    某个 provider 额度耗尽(HTTP 429/402)时自动冷却 1 小时。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认5
        topic: 搜索类型。'general' 通用搜索（默认），'news' 新闻搜索（优先返回近期资讯）
        save_to: 若指定文件路径，搜索结果追加写入 workspace/tmp 下（如 /tmp/research/x.md）
        phase: 搜索阶段标注（如"广度"/"深度"），写入文件时记录
        search_depth: 'basic'（默认）或 'advanced'（in-depth 调研时用，Tavily 等会加深检索）
    """
    from tools.safe_path import UnsafePathError, resolve_research_save_path
    from tools.search import SearchQuery, get_search_results

    async def _run() -> str:
        depth = (search_depth or "basic").strip().lower()
        if depth not in ("basic", "advanced"):
            depth = "basic"
        sq = SearchQuery(
            query=query,
            max_results=max_results,
            topic=topic,
            search_depth=depth,
            mode="fusion",
        )
        results, provider_name = await get_search_results(sq)
        if not results:
            return "没有找到相关结果"

        saved_path = ""
        if save_to:
            try:
                path = resolve_research_save_path(save_to)
                _append_research_to_file(
                    str(path), query, provider_name, results, topic, phase,
                )
                saved_path = str(path)
            except UnsafePathError as e:
                return f"搜索成功但落盘失败：{e}"

        parts = [f"[搜索来源: {provider_name} | 融合去重]"]
        if saved_path:
            parts.append(f"[搜索结果已保存到: {saved_path}]")

        refs: list[dict] = []
        for idx, r in enumerate(results):
            title = r.title or "（无标题）"
            url = r.url or ""
            snippet = (r.snippet or "（无摘要）")
            meta = []
            if getattr(r, "source_type", None):
                meta.append(r.source_type)
            if getattr(r, "domain", None):
                meta.append(r.domain)
            meta_s = f" ({', '.join(meta)})" if meta else ""
            entry = f"[{idx+1}] [{title}]({url or '（无链接）'}){meta_s}\n{snippet}"
            parts.append(entry)
            if url:
                refs.append({
                    "title": title,
                    "url": url,
                    "canonical_url": getattr(r, "canonical_url", "") or url,
                    "domain": getattr(r, "domain", "") or "",
                    "source_type": getattr(r, "source_type", "") or "general",
                    "snippet": snippet[:_SNIPPET_MAX],
                    "provider": getattr(r, "provider", "") or provider_name,
                    "published_at": getattr(r, "published_at", "") or "",
                    "score": getattr(r, "score", 0.0),
                })

        body = "\n\n---\n\n".join(parts)
        if refs:
            return f"{body}\n\n{_web_refs_marker(refs)}"
        return body

    try:
        return _run_coro(_run())
    except Exception as e:
        return f"搜索时出错：{str(e)}"
