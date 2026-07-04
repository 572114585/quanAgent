"""搜索 Provider 包:统一导出 failover 编排入口。

链路:Tavily → Brave → Serper → DuckDuckGo
"""
from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
from .tavily import TavilyProvider
from .brave import BraveProvider
from .serper import SerperProvider
from .duckduckgo import DuckDuckGoProvider
from .registry import get_search_results, reset_providers

__all__ = [
    "BaseSearchProvider",
    "SearchQuery",
    "SearchResult",
    "QuotaExceededError",
    "TavilyProvider",
    "BraveProvider",
    "SerperProvider",
    "DuckDuckGoProvider",
    "get_search_results",
    "reset_providers",
]
