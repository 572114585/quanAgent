import asyncio

import pytest

from tools.search import SearchQuery
from tools.search.base import BaseSearchProvider, SearchResult
from tools.search.registry import get_search_results, reset_providers


class FakeProvider(BaseSearchProvider):
    def __init__(self, name, results=None, error=None):
        super().__init__("key")
        self.name = name
        self.results = results or []
        self.error = error
        self.calls = 0

    def is_available(self):
        return True

    async def search(self, query):
        self.calls += 1
        if self.error:
            raise self.error
        return self.results


@pytest.mark.asyncio
async def test_first_non_empty_provider_stops_failover(monkeypatch):
    first = FakeProvider("tavily", [SearchResult("one", "https://example.com/1")])
    later = FakeProvider("brave", [SearchResult("two", "https://example.com/2")])
    import tools.search.registry as registry
    monkeypatch.setattr(registry, "_providers", [first, later])
    monkeypatch.setattr(registry, "_provider_loop", asyncio.get_running_loop())
    results, provider = await get_search_results(SearchQuery("q", max_results=99))
    assert provider == "tavily"
    assert len(results) == 1
    assert later.calls == 0
    reset_providers()


@pytest.mark.asyncio
async def test_empty_provider_fails_over_and_caps_results(monkeypatch):
    first = FakeProvider("tavily")
    later = FakeProvider("brave", [SearchResult(str(i), f"https://example.com/{i}") for i in range(10)])
    import tools.search.registry as registry
    monkeypatch.setattr(registry, "_providers", [first, later])
    monkeypatch.setattr(registry, "_provider_loop", asyncio.get_running_loop())
    results, provider = await get_search_results(SearchQuery("q", max_results=5))
    assert provider == "brave"
    assert len(results) == 3
    reset_providers()
