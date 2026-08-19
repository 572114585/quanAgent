#!/usr/bin/env python3
"""Fetch a public http(s) page and print candidate brand tokens.

Does not write skills/ or any style-guide file. The agent copies approved
values into tmp/diagram-design/style-guide.md.

    python skills/diagram-design/scripts/extract_brand.py --url https://example.com
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import socket
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_BYTES = 512 * 1024
TIMEOUT_S = 10
HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
CSS_VAR = re.compile(
    r"--([a-zA-Z0-9_-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))",
)
FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;{}]+)", re.IGNORECASE)
THEME_COLOR = re.compile(
    r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "metadata.google.internal",
    }
)


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http(s) URLs are allowed")
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise ValueError(f"blocked host: {host or '(empty)'}")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError(f"DNS failed for {host}: {exc}") from exc
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise ValueError(f"refusing non-public address {ip} for {host}")
    return url


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.styles: list[str] = []
        self.title_font = ""
        self.body_font = ""
        self._in_style = False
        self._in_title = False
        self._current = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k.lower(): (v or "") for k, v in attrs}
        style = data.get("style", "")
        if style:
            self.styles.append(style)
        if tag.lower() == "style":
            self._in_style = True
            self._current = ""
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._in_style:
            self.styles.append(self._current)
            self._in_style = False
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._current += data


def _fetch(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "quanAgent-diagram-design/1.0 (brand extract; public pages only)",
            "Accept": "text/html,application/xhtml+xml,text/css;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 — scheme/host validated above
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "html" not in content_type and "css" not in content_type and "text/" not in content_type:
            raise ValueError(f"unexpected content-type: {content_type or '(missing)'}")
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raw = raw[:MAX_BYTES]
    return raw.decode("utf-8", errors="replace")


def _rank_colors(html: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for match in HEX_COLOR.finditer(html):
        value = match.group(0).lower()
        if len(value) == 4:
            value = "#" + "".join(ch * 2 for ch in value[1:])
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print brand token candidates from a public URL (diagram-design skill).",
    )
    parser.add_argument("--url", required=True, help="Public http(s) homepage or docs URL.")
    args = parser.parse_args()
    try:
        url = _validate_url(args.url.strip())
        html = _fetch(url)
    except Exception as exc:  # noqa: BLE001 — agent-facing error string
        print(f"extract_brand: {exc}", file=sys.stderr)
        return 2

    collector = _Collector()
    try:
        collector.feed(html)
        collector.close()
    except Exception:
        pass

    css_blob = "\n".join(collector.styles)
    vars_found = [(name.lower(), value) for name, value in CSS_VAR.findall(html + "\n" + css_blob)]
    fonts = [item.strip().strip("\"'") for item in FONT_FAMILY.findall(html)]
    theme = ""
    theme_match = THEME_COLOR.search(html)
    if theme_match:
        theme = theme_match.group(1).strip()
    ranked = _rank_colors(html)

    print(f"# Brand extract from {url}")
    print()
    print("Do not write skills/. If the user approves, copy values into `tmp/diagram-design/style-guide.md`.")
    print()
    if theme:
        print(f"- meta theme-color: `{theme}`")
    if vars_found:
        print("- CSS custom properties:")
        for name, value in vars_found[:20]:
            print(f"  - `--{name}`: `{value}`")
    print()
    print("| Guessed role | Value | Why |")
    print("|---|---|---|")
    paper = next((c for c, _n in ranked if c in {"#ffffff", "#fff", "#fafafa", "#f5f5f5", "#f8f8f8"}), "")
    if not paper and ranked:
        paper = ranked[0][0]
    ink = next((c for c, _n in ranked if c in {"#000000", "#111111", "#1a1a1a", "#222222", "#2d3142"}), "")
    if not ink and len(ranked) > 1:
        ink = ranked[1][0]
    accent = theme if theme.startswith("#") else (ranked[2][0] if len(ranked) > 2 else "")
    print(f"| paper | `{paper or '(unknown)'}` | most frequent light hex / first color |")
    print(f"| ink | `{ink or '(unknown)'}` | common near-black / second color |")
    print(f"| accent | `{accent or '(unknown)'}` | theme-color or 3rd hex |")
    print()
    print("Top hex colors:")
    for color, count in ranked[:12]:
        print(f"- `{color}` × {count}")
    if fonts:
        print()
        print("font-family declarations:")
        for font in fonts[:8]:
            print(f"- `{font}`")
    print()
    print("Confidence is low without a rendered browser. Ask the user to confirm before applying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
