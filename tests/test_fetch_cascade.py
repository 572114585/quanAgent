"""web_fetch 三级兜底：403→Jina、直连短路、SSRF 拒绝。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.fetch_utils import (
    FetchAttempt,
    fetch_webpage_detailed,
    is_safe_target_url,
)


def test_direct_403_falls_back_to_jina(monkeypatch):
    monkeypatch.setenv("FETCH_JINA_ENABLED", "true")
    monkeypatch.setenv("FETCH_PLAYWRIGHT_ENABLED", "false")

    long_md = "# Fallback\n\n" + ("Jina readable content for cascade. " * 20)

    with (
        patch("tools.fetch_utils.fetch_direct") as mock_direct,
        patch("tools.fetch_utils.fetch_via_jina") as mock_jina,
        patch("tools.fetch_utils.fetch_via_playwright") as mock_pw,
        patch("tools.fetch_utils.is_safe_target_url", return_value=True),
    ):
        mock_direct.return_value = (
            "",
            FetchAttempt(channel="direct", ok=False, detail="403"),
        )
        mock_jina.return_value = (
            long_md,
            FetchAttempt(channel="jina", ok=True, detail="ok"),
        )

        result = fetch_webpage_detailed("https://example.com/blocked")

    assert result.ok
    assert result.channel == "jina"
    assert "Jina readable" in result.content
    assert [a.channel for a in result.attempts] == ["direct", "jina"]
    mock_pw.assert_not_called()


def test_direct_success_short_circuits_fallbacks(monkeypatch):
    monkeypatch.setenv("FETCH_JINA_ENABLED", "true")
    monkeypatch.setenv("FETCH_PLAYWRIGHT_ENABLED", "true")

    long_md = "# OK\n\n" + ("Direct fetch body is long enough to count. " * 20)

    with (
        patch("tools.fetch_utils.fetch_direct") as mock_direct,
        patch("tools.fetch_utils.fetch_via_jina") as mock_jina,
        patch("tools.fetch_utils.fetch_via_playwright") as mock_pw,
        patch("tools.fetch_utils.is_safe_target_url", return_value=True),
    ):
        mock_direct.return_value = (
            long_md,
            FetchAttempt(channel="direct", ok=True, detail="ok"),
        )

        result = fetch_webpage_detailed("https://example.com/ok")

    assert result.ok
    assert result.channel == "direct"
    mock_jina.assert_not_called()
    mock_pw.assert_not_called()


def test_unsafe_url_rejected_before_any_channel():
    with (
        patch("tools.fetch_utils.fetch_direct") as mock_direct,
        patch("tools.fetch_utils.fetch_via_jina") as mock_jina,
        patch("tools.fetch_utils.fetch_via_playwright") as mock_pw,
    ):
        result = fetch_webpage_detailed("http://127.0.0.1/secret")

    assert not result.ok
    assert result.content == ""
    assert result.attempts[0].detail == "unsafe"
    mock_direct.assert_not_called()
    mock_jina.assert_not_called()
    mock_pw.assert_not_called()


def test_is_safe_target_url_rejects_loopback_and_private():
    assert is_safe_target_url("http://127.0.0.1/") is False
    assert is_safe_target_url("http://localhost/") is False
    assert is_safe_target_url("http://192.168.1.1/") is False
    assert is_safe_target_url("ftp://example.com/") is False


def test_direct_403_httpx_then_jina_httpx(monkeypatch):
    """更贴近真实：mock httpx Client 直连 403，再 mock Jina GET 成功。"""
    monkeypatch.setenv("FETCH_JINA_ENABLED", "true")
    monkeypatch.setenv("FETCH_PLAYWRIGHT_ENABLED", "false")

    long_md = "# From Jina\n\n" + ("Readable markdown from reader proxy. " * 25)

    class FakeResp:
        def __init__(self, status_code: int, text: str = "", url: str = ""):
            self.status_code = status_code
            self.text = text
            self.url = url
            self.encoding = "utf-8"
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError(
                    "err",
                    request=MagicMock(),
                    response=self,
                )

        def iter_bytes(self, chunk_size=8192):
            yield b""

        def read(self):
            return b""

    class FakeStreamCM:
        def __init__(self, resp):
            self._resp = resp

        def __enter__(self):
            return self._resp

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self._timeout = kwargs.get("timeout")
            # Jina / direct 均不得自动跟随重定向（防 SSRF）
            assert kwargs.get("follow_redirects") is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return FakeStreamCM(FakeResp(403, url=url))

        def get(self, url, headers=None):
            assert url.startswith("https://r.jina.ai/")
            return FakeResp(200, text=long_md, url=url)

    with (
        patch("tools.fetch_utils.httpx.Client", FakeClient),
        patch("tools.fetch_utils.is_safe_target_url", return_value=True),
    ):
        result = fetch_webpage_detailed("https://vendor.example/blocked-page")

    assert result.ok
    assert result.channel == "jina"
    assert "From Jina" in result.content
    assert result.attempts[0].detail == "403"
    assert result.attempts[1].ok is True


def test_web_fetch_failure_message_lists_channels(monkeypatch):
    from tools.web_fetch import web_fetch

    monkeypatch.setenv("FETCH_JINA_ENABLED", "false")
    monkeypatch.setenv("FETCH_PLAYWRIGHT_ENABLED", "false")

    with (
        patch("tools.web_fetch.fetch_webpage_detailed") as mock_fetch,
        patch("tools.web_fetch.is_safe_target_url", return_value=True),
    ):
        from tools.fetch_utils import FetchResult

        mock_fetch.return_value = FetchResult(
            content="",
            attempts=[
                FetchAttempt(channel="direct", ok=False, detail="403"),
                FetchAttempt(channel="jina", ok=False, detail="disabled"),
                FetchAttempt(channel="playwright", ok=False, detail="disabled"),
            ],
        )
        out = web_fetch.invoke({"url": "https://example.com/x"})

    assert "抓取失败" in out
    assert "direct:403" in out
    assert "请立刻换" in out


def test_jina_disables_follow_redirects(monkeypatch):
    """Jina 通道必须 follow_redirects=False，3xx 记失败不跟随。"""
    monkeypatch.setenv("FETCH_JINA_ENABLED", "true")
    from tools.fetch_utils import fetch_via_jina

    seen: dict = {}

    class FakeResp:
        status_code = 302
        text = ""
        headers = {}

        def raise_for_status(self):
            raise AssertionError("should not raise on redirect")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            seen["follow_redirects"] = kwargs.get("follow_redirects")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return FakeResp()

    with (
        patch("tools.fetch_utils.httpx.Client", FakeClient),
        patch("tools.fetch_utils.is_safe_target_url", return_value=True),
    ):
        md, attempt = fetch_via_jina("https://example.com/page", 4000)

    assert md == ""
    assert attempt.ok is False
    assert attempt.detail.startswith("redirect:")
    assert seen["follow_redirects"] is False


def test_jina_rejects_private_url_before_request(monkeypatch):
    monkeypatch.setenv("FETCH_JINA_ENABLED", "true")
    from tools.fetch_utils import fetch_via_jina

    with patch("tools.fetch_utils.httpx.Client") as mock_client:
        md, attempt = fetch_via_jina("http://127.0.0.1/secret", 4000)

    assert md == ""
    assert attempt.detail == "unsafe"
    mock_client.assert_not_called()
