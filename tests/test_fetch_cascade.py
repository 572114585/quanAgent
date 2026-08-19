from unittest.mock import patch

from tools.fetch_utils import FetchAttempt, FetchResult, fetch_webpage_detailed, is_safe_target_url


def test_direct_success_does_not_call_jina():
    body = "# Page\n\n" + ("Readable direct content. " * 10)
    with patch("tools.fetch_utils.fetch_direct", return_value=(body, FetchAttempt("direct", True, "ok", "https://example.com"))), patch("tools.fetch_utils.fetch_via_jina") as jina, patch("tools.fetch_utils.is_safe_target_url", return_value=True):
        result = fetch_webpage_detailed("https://example.com")
    assert result.channel == "direct"
    jina.assert_not_called()


def test_failed_direct_uses_jina_once():
    body = "# Page\n\n" + ("Readable fallback content. " * 10)
    with patch("tools.fetch_utils.fetch_direct", return_value=("", FetchAttempt("direct", False, "403"))), patch("tools.fetch_utils.fetch_via_jina", return_value=(body, FetchAttempt("jina", True, "ok"))), patch("tools.fetch_utils.is_safe_target_url", return_value=True):
        result = fetch_webpage_detailed("https://example.com")
    assert result.channel == "jina"
    assert [attempt.channel for attempt in result.attempts] == ["direct", "jina"]


def test_remote_pdf_is_not_sent_to_mineru():
    with patch("tools.fetch_utils.fetch_direct", return_value=("", FetchAttempt("direct", False, "remote_pdf_upload_required"))), patch("tools.fetch_utils.fetch_via_jina", return_value=("", FetchAttempt("jina", False, "skipped"))) as jina, patch("tools.fetch_utils.is_safe_target_url", return_value=True):
        result = fetch_webpage_detailed("https://example.com/paper.pdf")
    assert not result.ok
    jina.assert_called_once()


def test_ssrf_protection_rejects_private_targets():
    assert not is_safe_target_url("http://127.0.0.1/secret")
    assert not is_safe_target_url("http://192.168.1.1/secret")
    assert not is_safe_target_url("ftp://example.com/file")
