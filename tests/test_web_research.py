import asyncio
import time

import httpx
import pytest

# Warm the package-level runtime configuration before measuring provider
# overlap; the application imports this once during process startup.
import agent_core.config  # noqa: F401

from tools.fetch_utils import FetchAttempt, FetchResult, fetch_webpages_batch
from tools.search.base import BaseSearchProvider, QuotaExceededError, SearchResult
from tools.search.registry import reset_providers, search_providers_parallel


class SlowProvider(BaseSearchProvider):
    def __init__(self, name: str, delay: float, results: list[SearchResult]):
        super().__init__("key")
        self.name = name
        self.delay = delay
        self.results = results
        self.calls = 0

    def is_available(self):
        return True

    async def search(self, query):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return self.results


class ErrorProvider(BaseSearchProvider):
    def __init__(self, name: str, error: Exception):
        super().__init__("key")
        self.name = name
        self.error = error
        self.calls = 0

    def is_available(self):
        return True

    async def search(self, query):
        self.calls += 1
        raise self.error


@pytest.mark.asyncio
async def test_parallel_provider_search_deduplicates_and_overlaps(monkeypatch):
    import tools.search.registry as registry

    result = SearchResult("same", "https://example.com/article", "summary")
    providers = [SlowProvider(f"p{i}", 0.08, [result]) for i in range(4)]
    monkeypatch.setattr(registry, "_providers", providers)
    monkeypatch.setattr(registry, "_provider_loop", asyncio.get_running_loop())

    started = time.perf_counter()
    batch = await search_providers_parallel(
        registry.SearchQuery("q", max_results=5),
        deadline_seconds=1,
        max_concurrency=3,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.25
    assert len(batch.results) == 1
    assert len(batch.providers) == 4
    assert batch.deadline_hit is False
    reset_providers()


@pytest.mark.asyncio
async def test_parallel_provider_search_returns_partial_on_deadline(monkeypatch):
    import tools.search.registry as registry

    fast = SlowProvider("fast", 0.01, [SearchResult("fast", "https://example.com/fast")])
    slow = SlowProvider("slow", 1.0, [SearchResult("slow", "https://example.com/slow")])
    monkeypatch.setattr(registry, "_providers", [fast, slow])
    monkeypatch.setattr(registry, "_provider_loop", asyncio.get_running_loop())

    batch = await search_providers_parallel(
        registry.SearchQuery("q"),
        deadline_seconds=0.08,
        max_concurrency=2,
    )

    assert [item.title for item in batch.results] == ["fast"]
    assert batch.deadline_hit is True
    assert batch.partial is True
    reset_providers()


@pytest.mark.asyncio
async def test_quota_is_cooled_without_retry_but_transient_5xx_retries_once(monkeypatch):
    import tools.search.registry as registry

    quota = ErrorProvider("quota", QuotaExceededError("402"))
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(503, request=request)
    transient = ErrorProvider("transient", httpx.HTTPStatusError("503", request=request, response=response))
    monkeypatch.setattr(registry, "_providers", [quota, transient])
    monkeypatch.setattr(registry, "_provider_loop", asyncio.get_running_loop())

    batch = await search_providers_parallel(
        registry.SearchQuery("q"), deadline_seconds=1, max_concurrency=2
    )

    assert quota.calls == 1
    assert transient.calls == 2
    assert quota._is_in_cooldown()
    assert batch.partial is True
    reset_providers()


@pytest.mark.asyncio
async def test_fetch_batch_is_bounded_and_independent(monkeypatch):
    import tools.fetch_utils as fetch_utils

    def fake_fetch(url, max_content_chars=6000):
        time.sleep(0.06)
        return FetchResult(
            content=(f"content for {url}. " * 20),
            channel="fake",
            final_url=url,
            attempts=[FetchAttempt("fake", True, "ok", url)],
            elapsed_ms=60,
        )

    monkeypatch.setattr(fetch_utils, "fetch_webpage_detailed", fake_fetch)
    started = time.perf_counter()
    results = await fetch_webpages_batch(
        ["https://example.com/1", "https://example.com/2", "https://example.com/3"],
        concurrency=3,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.2
    assert len(results) == 3
    assert all(result.ok for result in results.values())


def test_web_research_tool_returns_provenance_and_cache(monkeypatch):
    import tools.search.registry as registry
    import tools.web_search as web_search_module

    provider = SlowProvider(
        "mock",
        0,
        [SearchResult("Evidence", "https://example.com/evidence", "A useful summary")],
    )
    async def fake_get_providers():
        return [provider]

    monkeypatch.setattr(registry, "_get_providers", fake_get_providers)
    web_search_module._RESEARCH_CACHE.clear()

    first = web_search_module.web_research.invoke({"query": "unique evidence query"})
    second = web_search_module.web_research.invoke({"query": "unique evidence query"})

    assert '"provider": "mock"' in first
    assert "WEB_REFS" in first
    assert "research cache: hit" in second
    assert provider.calls == 1
