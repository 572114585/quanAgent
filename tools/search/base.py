from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class SearchQuery:
    query: str
    max_results: int = 3
    topic: str = "general"

    def __post_init__(self) -> None:
        self.max_results = max(1, min(int(self.max_results), 5))
        if self.topic not in {"general", "news"}:
            self.topic = "general"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    content: str = ""
    canonical_url: str = ""
    domain: str = ""
    provider: str = ""
    provider_rank: int = 0
    published_at: str = ""
    source_type: str = "general"
    score: float = 0.0

    def ensure_derived(self) -> None:
        from .url_utils import canonicalize_url, classify_source_type, extract_domain

        if not self.canonical_url and self.url:
            self.canonical_url = canonicalize_url(self.url)
        if not self.domain and (self.canonical_url or self.url):
            self.domain = extract_domain(self.canonical_url or self.url)
        if self.source_type == "general" and (self.url or self.title):
            self.source_type = classify_source_type(self.url, self.title)


class QuotaExceededError(Exception):
    """The provider should be cooled down before the next attempt."""


class BaseSearchProvider(ABC):
    name = "base"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self._cooldown_until = 0.0
        self.client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        self.client = client

    def mark_cooldown(self, seconds: int = 3600) -> None:
        self._cooldown_until = time.time() + seconds

    def _is_in_cooldown(self) -> bool:
        return time.time() < self._cooldown_until

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=6.0) as client:
            return await client.request(method, url, **kwargs)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError
