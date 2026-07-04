"""DuckDuckGo Provider(兜底)。

使用 ddgs 库抓取 DuckDuckGo 搜索结果。作为 failover 链路的最后一环,
永远可用(不受冷却影响),失败时抛普通 Exception 而非 QuotaExceededError。

DDGS 库本身是同步的,这里用 run_in_executor 包一层避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio
import logging

from .base import BaseSearchProvider, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


def _ddgs_search(query: str, max_results: int, topic: str) -> list[dict]:
    """同步执行 DDGS 搜索(在线程池中调用)。"""
    from ddgs import DDGS  # 延迟导入,避免无 DDG 环境下整个包加载失败

    with DDGS() as ddgs:
        if topic == "news":
            return list(ddgs.news(query, max_results=max_results))
        return list(ddgs.text(query, max_results=max_results))


class DuckDuckGoProvider(BaseSearchProvider):
    name = "duckduckgo"

    def __init__(self, api_key: str = ""):
        # DDG 不需要 key,忽略参数
        super().__init__(api_key="")

    def is_available(self) -> bool:
        # 兜底 provider:永远可用,不受冷却影响
        return True

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None, _ddgs_search, query.query, query.max_results, query.topic
        )

        results: list[SearchResult] = []
        for item in raw:
            # text 接口字段:title/href/body;news 接口:title/url/body
            title = item.get("title", "") or ""
            url = item.get("url") or item.get("href", "") or ""
            snippet = item.get("body", "") or ""
            results.append(SearchResult(title=title, url=url, snippet=snippet))
        return results
