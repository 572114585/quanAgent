"""URL 规范化、域名提取与来源类型启发式。"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# 跟踪参数：规范化时剥离
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
    }
)

_OFFICIAL_HINTS = (
    "docs.",
    "developer.",
    "developers.",
    "api.",
    "learn.",
    "help.",
    "support.",
    "www.gov",
    ".gov/",
    ".gov.",
    "arxiv.org",
    "ieee.org",
    "acm.org",
    "nature.com",
    "science.org",
    "springer.com",
    "github.com/",
    "gitlab.com/",
)

_NEWS_HINTS = (
    "news.",
    "reuters.com",
    "bloomberg.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "bbc.",
    "cnn.com",
    "nytimes.com",
    "ft.com",
    "wsj.com",
    "36kr.com",
    "sspai.com",
)

_PAPER_HINTS = (
    "arxiv.org",
    "acm.org",
    "ieee.org",
    "nature.com",
    "science.org",
    "springer.com",
    "sciencedirect.com",
    "openreview.net",
    "paperswithcode.com",
)


def canonicalize_url(url: str) -> str:
    """规范化 URL：小写 scheme/host、去 fragment、剥跟踪参数、去默认端口、去尾斜杠。"""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw

    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    if not netloc and parsed.path:
        # 容错：缺 scheme 的情况
        try:
            parsed = urlparse("https://" + raw)
            scheme = "https"
            netloc = (parsed.netloc or "").lower()
        except Exception:
            return raw

    # 去默认端口
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # 剥 www.
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # 过滤跟踪参数，保留其它 query（排序以保证稳定）
    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    pairs.sort(key=lambda x: (x[0], x[1]))
    query = urlencode(pairs, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_domain(url: str) -> str:
    """提取注册域风格 hostname（小写，去 www.）。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def classify_source_type(url: str, title: str = "") -> str:
    """启发式来源类型：official | paper | news | community | general。"""
    u = (url or "").lower()
    t = (title or "").lower()
    blob = f"{u} {t}"

    if any(h in blob for h in _PAPER_HINTS) or re.search(r"\b(arxiv|paper|doi)\b", blob):
        return "paper"
    if any(h in u for h in _OFFICIAL_HINTS) or "/docs/" in u or u.endswith(".gov"):
        return "official"
    if any(h in u for h in _NEWS_HINTS) or "news" in u.split("/")[2:3]:
        return "news"
    if any(
        x in u
        for x in (
            "reddit.com",
            "stackoverflow.com",
            "stackexchange.com",
            "medium.com",
            "zhihu.com",
            "juejin.cn",
            "dev.to",
            "hackernews",
            "news.ycombinator.com",
        )
    ):
        return "community"
    return "general"
