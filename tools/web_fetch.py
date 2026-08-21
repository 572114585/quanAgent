"""Explicit single-page web fetch tool."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from langchain_core.tools import tool

from tools.fetch_utils import (
    DEFAULT_MAX_CONTENT_CHARS,
    fetch_webpage_detailed,
    is_safe_target_url,
    wrap_external_content,
)


def _web_refs_marker(refs: list[dict]) -> str:
    return f"<!--WEB_REFS:{json.dumps(refs, ensure_ascii=False)}-->"


@tool
def web_fetch(url: str, max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS) -> str:
    """Fetch one user-requested HTTP(S) page; PDF URLs should be uploaded."""
    if not url or not url.strip():
        return "fetch failed: URL is empty"
    url = url.strip()
    if not is_safe_target_url(url):
        return "fetch failed: unsafe or unsupported URL"
    limit = max(1, min(int(max_content_chars), DEFAULT_MAX_CONTENT_CHARS))
    result = fetch_webpage_detailed(url, limit)
    if not result.ok:
        if any(attempt.detail == "remote_pdf_upload_required" for attempt in result.attempts):
            return "远程 PDF 不进入网页抓取链路，请先上传 PDF 文件，再使用文档处理能力。"
        return f"fetch failed ({result.failure_summary()}, elapsed_ms={result.elapsed_ms}): {url}"
    title = next(
        (line.lstrip("# ").strip() for line in result.content.splitlines() if line.strip().startswith("#")),
        urlparse(result.final_url or url).hostname or url,
    )
    body = f"[fetched via {result.channel}; elapsed_ms={result.elapsed_ms}] {title}\nURL: {result.final_url or url}\n\n"
    body += wrap_external_content(result.content[:limit], url=result.final_url or url, title=title)
    snippet = re.sub(r"\s+", " ", result.content).strip()[:500]
    refs = [{"title": title, "url": result.final_url or url, "snippet": snippet}]
    return f"{body}\n\n{_web_refs_marker(refs)}"
