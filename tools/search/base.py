"""搜索 Provider 抽象基类与数据结构。

所有第三方搜索 API(Tavily/Brave/Serper)与兜底的 DuckDuckGo
均实现 BaseSearchProvider,由 registry 按 failover / fusion 编排。
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    """搜索查询参数。"""

    query: str
    max_results: int = 5
    topic: str = "general"  # "general" | "news"
    search_depth: str = "basic"  # "basic" | "advanced"（Tavily 等支持时生效）
    # fusion 模式：并行拉多源后融合；failover：首个非空即返回（兼容旧行为）
    mode: str = "fusion"  # "fusion" | "failover"


@dataclass
class SearchResult:
    """统一的搜索结果条目。"""

    title: str
    url: str
    snippet: str = ""
    content: str = ""  # 可选正文(目前统一由 web_fetch 抓取,provider 不填)
    # --- 扩展元数据（融合 / 引用 / 时效） ---
    canonical_url: str = ""
    domain: str = ""
    provider: str = ""
    provider_rank: int = 0  # provider 内原始排名，0-based
    published_at: str = ""  # ISO 或原始日期字符串，可空
    source_type: str = "general"  # official|paper|news|community|general
    score: float = 0.0  # 融合后的排序分

    def ensure_derived(self) -> None:
        """补齐 canonical_url / domain / source_type（原地）。"""
        from .url_utils import canonicalize_url, classify_source_type, extract_domain

        if not self.canonical_url and self.url:
            self.canonical_url = canonicalize_url(self.url)
        if not self.domain and (self.canonical_url or self.url):
            self.domain = extract_domain(self.canonical_url or self.url)
        if self.source_type == "general" and (self.url or self.title):
            self.source_type = classify_source_type(self.url, self.title)


class QuotaExceededError(Exception):
    """Provider 免费额度耗尽时抛出,registry 据此切换到下一个 provider。

    各 provider 在识别到 HTTP 429/402 或响应体中的 quota/credits 错误时
    应抛出此异常,而非普通 Exception,以便 registry 区分"额度问题"与
    "网络抖动/临时故障"——前者需要冷却,后者只需跳过本次。
    """


class BaseSearchProvider(ABC):
    """搜索 Provider 抽象基类。

    子类需设置 self.name 并实现 search() 与 is_available()。
    冷却逻辑由基类提供:mark_cooldown() 设置冷却到期时间,
    is_available() 应调用 _is_in_cooldown() 判断。
    """

    name: str = "base"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self._cooldown_until: float = 0.0

    def mark_cooldown(self, seconds: int = 3600) -> None:
        """标记本 provider 在 seconds 秒内不可用。"""
        self._cooldown_until = time.time() + seconds

    def _is_in_cooldown(self) -> bool:
        return time.time() < self._cooldown_until

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """执行搜索,返回结果列表。额度耗尽时抛 QuotaExceededError。"""

    @abstractmethod
    def is_available(self) -> bool:
        """是否可用:key 已配置 且 不在冷却期。"""
