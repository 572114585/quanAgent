"""搜索 Provider 注册中心：failover 与 multi-provider fusion。

默认 mode=fusion：
  - 并行查询所有可用第三方 provider（+ 可选 DDG）
  - canonical URL 去重 + 域名多样性 + 权威/时效加权
  - 返回融合 Top-K

mode=failover（兼容旧行为）：
  - Tavily → Brave → Serper → DuckDuckGo 首个非空即返回
  - QuotaExceededError → 冷却 1 小时
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
from .tavily import TavilyProvider
from .brave import BraveProvider
from .serper import SerperProvider
from .duckduckgo import DuckDuckGoProvider
from .fuse import fuse_search_results

logger = logging.getLogger(__name__)

_providers: Optional[list[BaseSearchProvider]] = None
_init_lock = asyncio.Lock()


async def _get_providers() -> list[BaseSearchProvider]:
    """懒加载 provider 列表(线程安全)。"""
    global _providers
    if _providers is not None:
        return _providers

    async with _init_lock:
        if _providers is not None:
            return _providers

        from agent_core.config import (
            TAVILY_API_KEY,
            BRAVE_API_KEY,
            SERPER_API_KEY,
        )

        providers: list[BaseSearchProvider] = []
        if TAVILY_API_KEY:
            providers.append(TavilyProvider(TAVILY_API_KEY))
        if BRAVE_API_KEY:
            providers.append(BraveProvider(BRAVE_API_KEY))
        if SERPER_API_KEY:
            providers.append(SerperProvider(SERPER_API_KEY))
        providers.append(DuckDuckGoProvider())

        _providers = providers
        logger.info(
            "Search providers initialized (order): %s",
            [p.name for p in providers],
        )
        return _providers


async def _search_one(
    provider: BaseSearchProvider,
    query: SearchQuery,
    cooldown_seconds: int,
) -> tuple[str, list[SearchResult] | None, Exception | None]:
    """调用单个 provider，返回 (name, results|None, error|None)。"""
    if not provider.is_available():
        return provider.name, None, None
    try:
        results = await provider.search(query)
        for i, r in enumerate(results):
            r.provider = provider.name
            r.provider_rank = i
            r.ensure_derived()
        return provider.name, results or [], None
    except QuotaExceededError as e:
        provider.mark_cooldown(cooldown_seconds)
        logger.warning(
            "Provider %s quota exceeded, cooling down %ss: %s",
            provider.name,
            cooldown_seconds,
            e,
        )
        return provider.name, None, e
    except Exception as e:
        logger.warning(
            "Provider %s failed (transient, no cooldown): %s: %s",
            provider.name,
            type(e).__name__,
            e,
        )
        return provider.name, None, e


async def _get_search_results_failover(
    query: SearchQuery,
) -> tuple[list[SearchResult], str]:
    """旧链路：首个非空 provider 即返回。"""
    from agent_core.config import SEARCH_PROVIDER_COOLDOWN_SECONDS

    providers = await _get_providers()
    last_error: Optional[Exception] = None
    ddg_used_in_chain = False

    for provider in providers:
        if provider.name == "duckduckgo":
            ddg_used_in_chain = True
        name, results, err = await _search_one(
            provider, query, SEARCH_PROVIDER_COOLDOWN_SECONDS
        )
        if err is not None:
            last_error = err
            continue
        if results is None:
            continue
        if results:
            logger.info("Search succeeded via provider (failover): %s", name)
            return results, name
        logger.debug("Provider %s returned empty results", name)

    if not ddg_used_in_chain:
        try:
            ddg = DuckDuckGoProvider()
            results = await ddg.search(query)
            if results:
                for i, r in enumerate(results):
                    r.provider = ddg.name
                    r.provider_rank = i
                    r.ensure_derived()
                return results, ddg.name
        except Exception as e:
            last_error = e

    raise RuntimeError(f"所有搜索 provider 均不可用,最后错误: {last_error}")


async def _get_search_results_fusion(
    query: SearchQuery,
) -> tuple[list[SearchResult], str]:
    """并行多源融合。"""
    from agent_core.config import SEARCH_PROVIDER_COOLDOWN_SECONDS

    providers = await _get_providers()
    # 并行：所有已配置且可用的 provider（含 DDG）
    tasks = [
        _search_one(p, query, SEARCH_PROVIDER_COOLDOWN_SECONDS)
        for p in providers
        if p.is_available()
    ]
    if not tasks:
        # 全部冷却：仍强制试 DDG
        ddg = DuckDuckGoProvider()
        tasks = [_search_one(ddg, query, SEARCH_PROVIDER_COOLDOWN_SECONDS)]

    outcomes = await asyncio.gather(*tasks)
    batches: list[tuple[str, list[SearchResult]]] = []
    last_error: Optional[Exception] = None
    used_names: list[str] = []

    for name, results, err in outcomes:
        if err is not None:
            last_error = err
        if results:
            batches.append((name, results))
            used_names.append(name)

    if not batches:
        raise RuntimeError(f"所有搜索 provider 均不可用,最后错误: {last_error}")

    prefer_news = (query.topic or "").lower() == "news"
    fused = fuse_search_results(
        batches,
        max_results=max(1, query.max_results),
        max_per_domain=2,
        prefer_news=prefer_news,
    )
    if not fused:
        raise RuntimeError("融合后无有效搜索结果")

    provider_label = "+".join(used_names) if used_names else "fusion"
    logger.info(
        "Search fusion ok via [%s] → %s results",
        provider_label,
        len(fused),
    )
    return fused, provider_label


async def get_search_results(query: SearchQuery) -> tuple[list[SearchResult], str]:
    """按 query.mode 选择 fusion 或 failover，返回 (结果, provider 标签)。"""
    mode = (query.mode or "fusion").strip().lower()
    if mode == "failover":
        return await _get_search_results_failover(query)
    return await _get_search_results_fusion(query)


def reset_providers() -> None:
    """重置 provider 列表(主要供测试使用,运行时不应调用)。"""
    global _providers
    _providers = None
