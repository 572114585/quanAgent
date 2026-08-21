from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

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


@dataclass
class ProviderSearchAttempt:
    provider: str
    elapsed_ms: int = 0
    result_count: int = 0
    error: str = ""
    timed_out: bool = False


@dataclass
class SearchBatch:
    results: list[SearchResult] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    attempts: list[ProviderSearchAttempt] = field(default_factory=list)
    partial: bool = False
    deadline_hit: bool = False


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
        from agent_core.config import (
            BRAVE_API_KEY,
            SEARCH_PROVIDER_TIMEOUT_SECONDS,
            SERPER_API_KEY,
            TAVILY_API_KEY,
        )

        providers: list[BaseSearchProvider] = []
        for provider in (
            TavilyProvider(TAVILY_API_KEY),
            BraveProvider(BRAVE_API_KEY),
            SerperProvider(SERPER_API_KEY),
            DuckDuckGoProvider(),
        ):
            if provider.name == "duckduckgo" or provider.api_key:
                if provider.name != "duckduckgo":
                    provider.set_timeout(SEARCH_PROVIDER_TIMEOUT_SECONDS)
                    provider.set_client(httpx.AsyncClient(timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS))
                else:
                    provider.set_timeout(SEARCH_PROVIDER_TIMEOUT_SECONDS)
                providers.append(provider)
        _providers = providers
        _provider_loop = current_loop
        return providers


async def _search_one(
    provider: BaseSearchProvider, query: SearchQuery, cooldown_seconds: int
) -> tuple[list[SearchResult] | None, Exception | None]:
    if not provider.is_available():
        return None, None

    async def invoke() -> list[SearchResult]:
        try:
            return await provider.search(query)
        except httpx.HTTPStatusError as exc:
            # A transient upstream 5xx gets one short retry. Quota and auth
            # failures are handled below and are never retried here.
            status = exc.response.status_code if exc.response is not None else 0
            if 500 <= status < 600:
                await asyncio.sleep(0.15)
                return await provider.search(query)
            raise

    try:
        results = await invoke()
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


async def search_providers_parallel(
    query: SearchQuery,
    *,
    deadline_seconds: float | None = None,
    max_concurrency: int | None = None,
) -> SearchBatch:
    """Search all available providers concurrently with bounded cancellation.

    This is intentionally separate from the legacy serial failover path so
    integrations that depend on first-provider semantics remain compatible.
    """
    from agent_core.config import (
        SEARCH_PROVIDER_CONCURRENCY,
        SEARCH_PROVIDER_COOLDOWN_SECONDS,
        SEARCH_PROVIDER_TIMEOUT_SECONDS,
    )

    providers = await _get_providers()
    limit = max(1, int(max_concurrency or SEARCH_PROVIDER_CONCURRENCY))
    semaphore = asyncio.Semaphore(limit)
    started = time.perf_counter()
    batch = SearchBatch()

    async def run(provider: BaseSearchProvider) -> tuple[list[SearchResult] | None, ProviderSearchAttempt]:
        if not provider.is_available():
            return None, ProviderSearchAttempt(provider.name, error="cooldown_or_unavailable")
        attempt_started = time.perf_counter()
        async with semaphore:
            try:
                operation = _search_one(provider, query, SEARCH_PROVIDER_COOLDOWN_SECONDS)
                if deadline_seconds is None:
                    results, error = await operation
                else:
                    remaining = max(0.1, deadline_seconds - (time.perf_counter() - started))
                    results, error = await asyncio.wait_for(operation, timeout=remaining)
                attempt = ProviderSearchAttempt(
                    provider=provider.name,
                    elapsed_ms=int((time.perf_counter() - attempt_started) * 1000),
                    result_count=len(results or []),
                    error=type(error).__name__ if error else "",
                )
                return results, attempt
            except asyncio.TimeoutError:
                return None, ProviderSearchAttempt(
                    provider=provider.name,
                    elapsed_ms=int((time.perf_counter() - attempt_started) * 1000),
                    error="timeout",
                    timed_out=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive boundary
                return None, ProviderSearchAttempt(
                    provider=provider.name,
                    elapsed_ms=int((time.perf_counter() - attempt_started) * 1000),
                    error=type(exc).__name__,
                )

    tasks = [asyncio.create_task(run(provider)) for provider in providers]
    try:
        if deadline_seconds is None:
            completed = await asyncio.gather(*tasks)
        else:
            completed, pending = await asyncio.wait(
                tasks,
                timeout=max(0.1, deadline_seconds),
            )
            if pending:
                batch.deadline_hit = True
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            completed = [task.result() for task in completed if not task.cancelled() and task.exception() is None]
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[SearchResult] = []
    for results, attempt in completed:
        batch.attempts.append(attempt)
        if results:
            batch.providers.append(attempt.provider)
            all_results.extend(results)

    # Stable dedupe by canonical URL, then title/domain for providers that
    # return tracking URLs or incomplete links.
    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for result in all_results:
        result.ensure_derived()
        key = result.canonical_url or f"{result.domain}:{result.title.casefold().strip()}"
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    batch.results = deduped[: max(3, query.max_results)]
    batch.partial = batch.deadline_hit or any(a.error for a in batch.attempts)
    return batch


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
