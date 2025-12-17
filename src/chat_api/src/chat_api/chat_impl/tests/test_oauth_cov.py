import asyncio
import types
import sys
import pytest

from slack_impl.oauth import (
    _get_env,
    build_authorization_url,
    exchange_code_for_tokens,
)


def test_get_env_and_build_authorization_url_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLACK_CLIENT_ID", "CID123")
    monkeypatch.setenv("SLACK_REDIRECT_URI", "https://app.example/callback")
    monkeypatch.setenv("SLACK_SCOPES", "channels:read chat:write")

    url = build_authorization_url(state="abc123")
    assert "client_id=CID123" in url
    assert "redirect_uri=https%3A%2F%2Fapp.example%2Fcallback" in url
    assert "scope=channels%3Aread+chat%3Awrite" in url
    assert "state=abc123" in url


def test_get_env_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOTALLY_MISSING_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _get_env("TOTALLY_MISSING_ENV")


def test_exchange_code_for_tokens_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # Provide required env
    monkeypatch.setenv("SLACK_CLIENT_ID", "CID123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "SECRET456")
    monkeypatch.setenv("SLACK_REDIRECT_URI", "https://app.example/cb")

    # Dummy httpx AsyncClient replacement that returns ok=True
    class DummyResp:
        def raise_for_status(self) -> None:
            return

        def json(self):
            return {
                "ok": True,
                "access_token": "xoxb-abc",
                "token_type": "Bearer",
                "scope": "chat:write",
            }

    class DummyAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            assert "client_id" in data and "client_secret" in data and "code" in data
            return DummyResp()

    # Create a synthetic "httpx" module so the inner import uses it
    dummy_httpx_mod = types.ModuleType("httpx")
    dummy_httpx_mod.AsyncClient = DummyAsyncClient  # type: ignore[attr-defined]

    # Patch sys.modules so `import httpx` inside the function grabs our dummy
    monkeypatch.setitem(sys.modules, "httpx", dummy_httpx_mod)

    # Run coroutine without pytest-asyncio
    result = asyncio.run(exchange_code_for_tokens("the-code", redirect_uri=None))
    assert getattr(result, "access_token", "") == "xoxb-abc"
    assert getattr(result, "token_type", "") == "Bearer"

def test_exchange_code_for_tokens_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Provide required env variables
    monkeypatch.setenv("SLACK_CLIENT_ID", "CID123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "SECRET456")
    monkeypatch.setenv("SLACK_REDIRECT_URI", "https://app.example/cb")

    # Dummy httpx AsyncClient that simulates Slack returning ok=False
    class DummyResp:
        def __init__(self) -> None:
            self._payload = {
                "ok": False,
                "error": "invalid_code",
            }

        def raise_for_status(self) -> None:
            # HTTP-level success, but Slack-level failure
            return

        def json(self):
            return self._payload

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            # Simulate posting to Slack OAuth token endpoint
            assert "client_id" in data and "client_secret" in data and "code" in data
            return DummyResp()

    # Inject our dummy httpx module so the inner import in oauth.py uses it
    dummy_httpx_mod = types.ModuleType("httpx")
    dummy_httpx_mod.AsyncClient = DummyAsyncClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", dummy_httpx_mod)

    # When Slack says ok=False, we expect some kind of exception
    with pytest.raises(Exception):
        asyncio.run(exchange_code_for_tokens("bad-code", redirect_uri=None))
