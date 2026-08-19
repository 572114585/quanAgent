from __future__ import annotations

import asyncio
import logging

import httpx

from .base import BaseSearchProvider, QuotaExceededError, SearchQuery, SearchResult
from .brave import BraveProvider
from .duckduckgo import DuckDuckGoProvider
from .serper import SerperProvider
from .tavily import TavilyProvider

logger = logging.getLogger(__name__)
_providers: list[BaseSearchProvider] | None = None
_provider_loop: asyncio.AbstractEventLoop | None = None
_init_lock = asyncio.Lock()


async def _get_providers() -> list[BaseSearchProvider]:
    global _providers, _provider_loop
    current_loop = asyncio.get_running_loop()
    if _providers is not None and _provider_loop is not current_loop:
        await asyncio.gather(*(provider.close() for provider in _providers))
        _providers = None
    if _providers is not None:
        return _providers
    async with _init_lock:
        if _providers is not None:
            return _providers
        from agent_core.config import BRAVE_API_KEY, SERPER_API_KEY, TAVILY_API_KEY

        providers: list[BaseSearchProvider] = []
        for provider in (
            TavilyProvider(TAVILY_API_KEY),
            BraveProvider(BRAVE_API_KEY),
            SerperProvider(SERPER_API_KEY),
            DuckDuckGoProvider(),
        ):
            if provider.name == "duckduckgo" or provider.api_key:
                if provider.name != "duckduckgo":
                    provider.set_client(httpx.AsyncClient(timeout=6.0))
                providers.append(provider)
        _providers = providers
        _provider_loop = current_loop
        return providers


async def _search_one(
    provider: BaseSearchProvider, query: SearchQuery, cooldown_seconds: int
) -> tuple[list[SearchResult] | None, Exception | None]:
    if not provider.is_available():
        return None, None
    try:
        results = await provider.search(query)
        for rank, result in enumerate(results):
            result.provider = provider.name
            result.provider_rank = rank
            result.ensure_derived()
        return results[: query.max_results], None
    except QuotaExceededError as exc:
        provider.mark_cooldown(cooldown_seconds)
        logger.warning("Search provider %s cooled down: %s", provider.name, exc)
        return None, exc
    except Exception as exc:  # transient provider failure; try the next one
        logger.warning("Search provider %s failed: %s", provider.name, exc)
        return None, exc


async def get_search_results(query: SearchQuery) -> tuple[list[SearchResult], str]:
    """Search providers serially and return on the first non-empty result."""
    from agent_core.config import SEARCH_PROVIDER_COOLDOWN_SECONDS

    providers = await _get_providers()
    last_error: Exception | None = None
    for provider in providers:
        results, error = await _search_one(
            provider, query, SEARCH_PROVIDER_COOLDOWN_SECONDS
        )
        if error is not None:
            last_error = error
        if results:
            return results[:3], provider.name
    raise RuntimeError(f"all search providers failed or returned no results: {last_error}")


async def close_providers() -> None:
    global _providers, _provider_loop
    providers, _providers = _providers, None
    _provider_loop = None
    if providers:
        await asyncio.gather(*(provider.close() for provider in providers))


def reset_providers() -> None:
    """Reset the registry for isolated tests; production uses close_providers."""
    global _providers, _provider_loop
    _providers = None
    _provider_loop = None
