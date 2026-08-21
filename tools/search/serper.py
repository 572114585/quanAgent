"""Serper Provider(Google SERP API)。

官方文档:https://serper.dev/
认证:X-API-KEY 头
免费额度:2500 次一次性,超额返回 429 或 402。
返回原始 Google SERP,需自行解析 organic 字段。
"""
from __future__ import annotations

import logging

import httpx

from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError

logger = logging.getLogger(__name__)

_SERPER_URL = "https://google.serper.dev/search"
_SERPER_NEWS_URL = "https://google.serper.dev/news"


class SerperProvider(BaseSearchProvider):
    name = "serper"

    def is_available(self) -> bool:
        return bool(self.api_key) and not self._is_in_cooldown()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        body = {"q": query.query, "num": query.max_results}
        url = _SERPER_NEWS_URL if query.topic == "news" else _SERPER_URL

        resp = await self.request("POST", url, headers=headers, json=body, timeout=self.timeout)

        # 错误码识别
        if resp.status_code in (429, 402):
            logger.warning(
                "Serper quota exceeded (HTTP %s), will cool down.", resp.status_code
            )
            raise QuotaExceededError(f"Serper HTTP {resp.status_code}")

        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"Serper non-JSON response: {resp.text[:200]}")

        # 部分配额错误以 JSON error 字段返回
        err = data.get("error")
        if isinstance(err, str) and any(
            kw in err.lower() for kw in ("credits", "quota", "exceeded", "balance")
        ):
            logger.warning("Serper quota exceeded (body error): %s", err)
            raise QuotaExceededError(f"Serper body error: {err}")

        results: list[SearchResult] = []
        # Serper 通用搜索:{"organic": [...]}
        # Serper 新闻搜索:{"news": [...]}
        items = data.get("organic") or data.get("news") or []
        for i, item in enumerate(items):
            r = SearchResult(
                title=item.get("title", "") or "",
                url=item.get("link", "") or "",
                snippet=item.get("snippet", "") or "",
                provider="serper",
                provider_rank=i,
                published_at=str(item.get("date") or item.get("publishedAt") or ""),
            )
            r.ensure_derived()
            results.append(r)
        return results
