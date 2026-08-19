"""Tavily Search Provider。

官方文档:https://docs.tavily.com/documentation/api-reference/endpoint/search
认证:Bearer token(API key)
免费额度:1000 次/月,超额返回 429。
"""
from __future__ import annotations

import logging

import httpx

from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class TavilyProvider(BaseSearchProvider):
    name = "tavily"

    def is_available(self) -> bool:
        return bool(self.api_key) and not self._is_in_cooldown()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "query": query.query,
            "max_results": query.max_results,
            "topic": query.topic,  # "general" | "news"
            "include_answer": False,
            "include_raw_content": False,  # 省额度,正文由 web_fetch + save_to 落盘
        }
        resp = await self.request("POST", _TAVILY_URL, headers=headers, json=body,
                                  timeout=6.0)

        # 错误码识别:429 Too Many Requests / 402 Payment Required
        if resp.status_code in (429, 402):
            logger.warning(
                "Tavily quota exceeded (HTTP %s), will cool down.", resp.status_code
            )
            raise QuotaExceededError(f"Tavily HTTP {resp.status_code}")

        # 200 但响应体里带 error 字段(部分配额错误以此形式返回)
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            raise RuntimeError(f"Tavily non-JSON response: {resp.text[:200]}")

        err = data.get("error")
        if isinstance(err, str) and any(
            kw in err.lower() for kw in ("quota", "limit", "credits", "exceeded")
        ):
            logger.warning("Tavily quota exceeded (body error): %s", err)
            raise QuotaExceededError(f"Tavily body error: {err}")

        resp.raise_for_status()

        results: list[SearchResult] = []
        for i, item in enumerate(data.get("results", []) or []):
            r = SearchResult(
                title=item.get("title", "") or "",
                url=item.get("url", "") or "",
                snippet=item.get("content", "") or "",
                provider="tavily",
                provider_rank=i,
                published_at=str(item.get("published_date") or item.get("published_at") or ""),
            )
            r.ensure_derived()
            results.append(r)
        return results
