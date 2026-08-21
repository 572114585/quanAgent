"""Fast, summary-only web search."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
import time

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


def _format_results(results, providers: list[str], *, partial: bool = False, deadline_hit: bool = False) -> str:
    parts = [f"[search providers: {', '.join(providers) or 'none'}]"]
    if partial or deadline_hit:
        parts.append(f"[search status: partial={partial} deadline_hit={deadline_hit}]")
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
                "provider": result.provider,
            })
    body = "\n\n---\n\n".join(parts)
    return f"{body}\n\n{_web_refs_marker(refs)}" if refs else body


@tool
def web_search(query: str, max_results: int = 3, topic: str = "general") -> str:
    """Search the web and return at most three title/URL/summary entries.

    Use web_fetch only when the user explicitly asks to open a URL or read a
    page. Search never saves files and never fetches result pages implicitly.
    """
    from tools.search import SearchQuery
    from tools.search.registry import search_providers_parallel

    async def run() -> str:
        batch = await search_providers_parallel(
            SearchQuery(query=query, max_results=max_results, topic=topic),
            deadline_seconds=10.0,
        )
        return _format_results(
            batch.results,
            batch.providers,
            partial=batch.partial,
            deadline_hit=batch.deadline_hit,
        )

    try:
        return _run_coro(run())
    except Exception as exc:
        return f"search failed: {exc}"


_RESEARCH_CACHE: dict[tuple[str, str], tuple[float, str]] = {}
_RESEARCH_CACHE_TTL_SECONDS = 300.0
_RESEARCH_BUDGET_LOCK = threading.Lock()
_RESEARCH_WINDOW_STARTED = 0.0
_RESEARCH_WINDOW_COUNT = 0


def _claim_research_budget(limit: int, window_seconds: float) -> bool:
    global _RESEARCH_WINDOW_STARTED, _RESEARCH_WINDOW_COUNT
    now = time.monotonic()
    with _RESEARCH_BUDGET_LOCK:
        if now - _RESEARCH_WINDOW_STARTED >= window_seconds:
            _RESEARCH_WINDOW_STARTED = now
            _RESEARCH_WINDOW_COUNT = 0
        if _RESEARCH_WINDOW_COUNT >= max(1, limit):
            return False
        _RESEARCH_WINDOW_COUNT += 1
        return True


@tool
def web_research(
    query: str,
    topic: str = "general",
    max_workers: int = 4,
    max_queries: int = 6,
    deadline_seconds: float = 55,
) -> str:
    """Run a bounded, provider-parallel research search.

    This tool returns source summaries only. It never fetches pages implicitly;
    use web_fetch for explicitly selected URLs. Multiple research subagents can
    call it concurrently, while provider concurrency and query budgets remain
    bounded by runtime configuration.
    """
    del max_workers  # worker fan-out is owned by the parent DeepAgent
    from agent_core.config import (
        SEARCH_PROVIDER_CONCURRENCY,
        WEB_RESEARCH_DEADLINE_SECONDS,
        WEB_RESEARCH_MAX_QUERIES,
    )
    from tools.search import SearchQuery
    from tools.search.registry import search_providers_parallel

    normalized_query = " ".join((query or "").split())
    if not normalized_query:
        return "research failed: query is empty"
    effective_topic = topic if topic in {"general", "news"} else "general"
    effective_deadline = max(1.0, min(float(deadline_seconds or WEB_RESEARCH_DEADLINE_SECONDS), WEB_RESEARCH_DEADLINE_SECONDS))
    key = (normalized_query.casefold(), effective_topic)
    cached = _RESEARCH_CACHE.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _RESEARCH_CACHE_TTL_SECONDS:
        return f"[research cache: hit]\n{cached[1]}"
    if not _claim_research_budget(
        min(max(1, int(max_queries)), WEB_RESEARCH_MAX_QUERIES),
        effective_deadline,
    ):
        return "research partial: shared query budget exhausted"

    async def run() -> str:
        batch = await search_providers_parallel(
            SearchQuery(normalized_query, max_results=5, topic=effective_topic),
            deadline_seconds=effective_deadline,
            max_concurrency=SEARCH_PROVIDER_CONCURRENCY,
        )
        refs = [
            {
                "title": result.title or "(untitled)",
                "url": result.url,
                "snippet": (result.snippet or "").strip()[:_SNIPPET_MAX],
                "provider": result.provider,
                "domain": result.domain,
                "source_type": result.source_type,
            }
            for result in batch.results[:5]
            if result.url
        ]
        metadata = {
            "providers": batch.providers,
            "attempts": [a.__dict__ for a in batch.attempts],
            "result_count": len(batch.results),
            "partial": batch.partial,
            "deadline_hit": batch.deadline_hit,
            "elapsed_ms": max((a.elapsed_ms for a in batch.attempts), default=0),
        }
        body = json.dumps({"query": normalized_query, "metadata": metadata, "results": refs}, ensure_ascii=False, indent=2)
        return f"[web_research]\n{body}\n\n{_web_refs_marker(refs)}"

    try:
        value = _run_coro(run())
        _RESEARCH_CACHE[key] = (time.monotonic(), value)
        return value
    except Exception as exc:
        return f"research failed: {exc}"
