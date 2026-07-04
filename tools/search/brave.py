"""Brave Search Provider。

官方文档:https://api-dashboard.search.brave.com/
认证:X-Subscription-Token 头
免费额度:每月 $5 credits,超额返回 429 或 402。
"""
from __future__ import annotations

import logging

import httpx

from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError

logger = logging.getLogger(__name__)

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_TIMEOUT = 10.0


class BraveProvider(BaseSearchProvider):
    name = "brave"

    def is_available(self) -> bool:
        return bool(self.api_key) and not self._is_in_cooldown()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        headers = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json",
        }
        params = {
            "q": query.query,
            "count": query.max_results,
        }
        # Brave 用单独的 news 端点;为保持简单,这里仍用 web 端点
        # (news 端点需要额外订阅,免费层不一定支持)
        async with httpx.AsyncClient(timeout=_BRAVE_TIMEOUT) as client:
            resp = await client.get(_BRAVE_URL, headers=headers, params=params)

        # 错误码识别
        if resp.status_code in (429, 402):
            logger.warning(
                "Brave quota exceeded (HTTP %s), will cool down.", resp.status_code
            )
            raise QuotaExceededError(f"Brave HTTP {resp.status_code}")

        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"Brave non-JSON response: {resp.text[:200]}")

        results: list[SearchResult] = []
        # Brave 响应结构:{"web": {"results": [...]}}
        web_block = data.get("web") or {}
        for item in web_block.get("results", []) or []:
            results.append(
                SearchResult(
                    title=item.get("title", "") or "",
                    url=item.get("url", "") or "",
                    snippet=item.get("description", "") or "",
                )
            )
        return results
