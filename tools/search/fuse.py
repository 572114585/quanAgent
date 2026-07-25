"""多 Provider 搜索结果融合：去重、域名多样性、权威/时效加权。"""
from __future__ import annotations

from .base import SearchResult
from .url_utils import canonicalize_url, classify_source_type, extract_domain

# 来源类型加权
_TYPE_BONUS = {
    "official": 3.0,
    "paper": 2.5,
    "news": 1.5,
    "community": 0.5,
    "general": 1.0,
}

# Provider 基础可信度（相对）
_PROVIDER_BONUS = {
    "tavily": 1.5,
    "brave": 1.2,
    "serper": 1.3,
    "duckduckgo": 0.5,
}


def fuse_search_results(
    batches: list[tuple[str, list[SearchResult]]],
    *,
    max_results: int = 8,
    max_per_domain: int = 2,
    prefer_news: bool = False,
) -> list[SearchResult]:
    """融合多个 (provider_name, results) 批次。

    步骤：
      1. 补齐元数据 + canonical URL 去重（保留高分）
      2. 打分：provider 排名 + 类型加权 + provider 可信度 + 新闻偏好
      3. 按域名多样性截断（同域最多 max_per_domain）
      4. 返回 Top max_results
    """
    best_by_canon: dict[str, SearchResult] = {}

    for provider_name, results in batches:
        for rank, r in enumerate(results):
            if not (r.url or "").strip():
                continue
            r.provider = r.provider or provider_name
            r.provider_rank = rank
            r.ensure_derived()
            if not r.canonical_url:
                r.canonical_url = canonicalize_url(r.url)
            if not r.domain:
                r.domain = extract_domain(r.canonical_url or r.url)
            if r.source_type == "general":
                r.source_type = classify_source_type(r.url, r.title)

            r.score = _score(r, prefer_news=prefer_news)
            key = r.canonical_url or r.url
            prev = best_by_canon.get(key)
            if prev is None or r.score > prev.score:
                best_by_canon[key] = r

    ranked = sorted(best_by_canon.values(), key=lambda x: x.score, reverse=True)

    # 域名多样性
    out: list[SearchResult] = []
    domain_count: dict[str, int] = {}
    for r in ranked:
        dom = r.domain or extract_domain(r.url) or "_"
        if domain_count.get(dom, 0) >= max_per_domain:
            continue
        domain_count[dom] = domain_count.get(dom, 0) + 1
        out.append(r)
        if len(out) >= max_results:
            break

    return out


def _score(r: SearchResult, *, prefer_news: bool) -> float:
    # 排名衰减：第 1 名 10 分，之后递减
    rank_score = max(0.0, 10.0 - float(r.provider_rank) * 1.2)
    type_bonus = _TYPE_BONUS.get(r.source_type, 1.0)
    provider_bonus = _PROVIDER_BONUS.get(r.provider, 0.8)
    news_bonus = 0.0
    if prefer_news and r.source_type == "news":
        news_bonus = 2.0
    # 有发布时间略加分（能做时效判断）
    date_bonus = 0.5 if (r.published_at or "").strip() else 0.0
    # 摘要长度：过短惩罚
    snip = (r.snippet or "").strip()
    snip_bonus = 0.5 if len(snip) >= 80 else (0.0 if snip else -0.5)
    return rank_score + type_bonus + provider_bonus + news_bonus + date_bonus + snip_bonus
