"""Web Bearer 鉴权与 HOST 回环校验。"""
from __future__ import annotations

from entrypoints.web import check_bearer_auth, is_loopback_host


def test_is_loopback_host():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("::1")
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("192.168.1.10")


def test_check_bearer_auth_open_when_no_token():
    assert check_bearer_auth(None, "") is True
    assert check_bearer_auth("Bearer anything", "") is True


def test_check_bearer_auth_requires_match():
    assert check_bearer_auth("Bearer secret", "secret") is True
    assert check_bearer_auth("Bearer wrong", "secret") is False
    assert check_bearer_auth(None, "secret") is False
    assert check_bearer_auth("secret", "secret") is False


def test_chat_requires_bearer_when_token_set(monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-secret-token")
    from fastapi.testclient import TestClient

    from entrypoints.web import app

    client = TestClient(app)
    r = client.post("/chat", json={"sessionId": "s1", "message": "hi"})
    assert r.status_code == 401
    assert r.json().get("message") == "Unauthorized"

    # 带正确 token：鉴权通过（可能因 agent 初始化失败返回 503，但不该是 401）
    r2 = client.post(
        "/chat",
        json={"sessionId": "s1", "message": "hi"},
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert r2.status_code != 401


def test_health_open_without_token(monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-secret-token")
    from fastapi.testclient import TestClient

    from entrypoints.web import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
