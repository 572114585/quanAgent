"""Fast, summary-only web search."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json

from langchain_core.tools import tool

_SNIPPET_MAX = 500


def _run_coro(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _web_refs_marker(refs: list[dict]) -> str:
    return f"<!--WEB_REFS:{json.dumps(refs, ensure_ascii=False)}-->"


@tool
def web_search(query: str, max_results: int = 3, topic: str = "general") -> str:
    """Search the web and return at most three title/URL/summary entries.

    Use web_fetch only when the user explicitly asks to open a URL or read a
    page. Search never saves files and never fetches result pages implicitly.
    """
    from tools.search import SearchQuery, get_search_results

    async def run() -> str:
        results, provider = await get_search_results(
            SearchQuery(query=query, max_results=max_results, topic=topic)
        )
        parts = [f"[search provider: {provider}]"]
        refs: list[dict] = []
        for index, result in enumerate(results[:3], 1):
            title = result.title or "(untitled)"
            url = result.url or ""
            snippet = (result.snippet or "(no summary)").strip()[:_SNIPPET_MAX]
            parts.append(f"[{index}] [{title}]({url})\n{snippet}")
            if url:
                refs.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "provider": result.provider or provider,
                })
        body = "\n\n---\n\n".join(parts)
        return f"{body}\n\n{_web_refs_marker(refs)}" if refs else body

    try:
        return _run_coro(run())
    except Exception as exc:
        return f"search failed: {exc}"
