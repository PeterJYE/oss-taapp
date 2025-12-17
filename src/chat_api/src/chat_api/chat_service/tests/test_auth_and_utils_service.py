from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from slack_service.app import (
    app,
    _build_slack_authorize_url,
    _check_state,
    _make_state,
)
from slack_impl.token_store import SQLiteTokenStore, TokenBundle

slack_app_module = importlib.import_module("slack_service.app")


def test_auth_status_unauthenticated_false() -> None:
    client = TestClient(app)
    resp = client.get("/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["user_id"] is None


def test_logout_ok_without_tokens() -> None:
    client = TestClient(app)
    resp = client.delete("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_make_and_check_state_roundtrip() -> None:
    secret = "state-secret"
    state = _make_state(secret, ttl_sec=60)
    assert _check_state(state, secret, ttl_sec=60) is True


def test_check_state_rejects_tampered_state() -> None:
    secret = "state-secret"
    state = _make_state(secret, ttl_sec=60)
    bad_state = state + "x"
    assert _check_state(bad_state, secret, ttl_sec=60) is False


def test_build_slack_authorize_url_contains_expected_params() -> None:
    url = _build_slack_authorize_url(
        client_id="cid",
        redirect_uri="http://localhost/callback",
        state="abc",
        user_scope_csv="u1,u2",
        bot_scope_csv="b1,b2",
    )
    assert url.startswith("https://slack.com/oauth/v2/authorize?")
    assert "client_id=cid" in url
    assert "state=abc" in url
    assert "user_scope=u1%2Cu2" in url
    assert "scope=b1%2Cb2" in url


def test_debug_login_url_uses_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost/callback")

    client = TestClient(app)
    resp = client.get("/__debug/login-url", params={"state": "xyz"})
    assert resp.status_code == 200
    data = resp.json()
    url = data["url"]
    assert "client_id=cid" in url
    assert "state=xyz" in url


def test_auth_login_redirects_to_slack(monkeypatch) -> None:
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost/callback")

    client = TestClient(app)
    # httpx-based TestClient uses `follow_redirects`
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert location.startswith("https://slack.com/oauth/v2/authorize")
    assert "client_id=cid" in location


def _make_test_store() -> SQLiteTokenStore:
    """Create an in-memory SQLiteTokenStore and install it into the service module."""
    store = SQLiteTokenStore(":memory:")
    slack_app_module._store = store
    return store


class FakeWebClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def conversations_create(self, name: str, is_private: bool = False) -> dict:
        return {"channel": {"id": "C999", "name": name}}

    def conversations_rename(self, channel: str, name: str) -> dict:
        return {"channel": {"id": channel, "name": name}}

    def conversations_archive(self, channel: str) -> dict:
        return {}

    def conversations_join(self, channel: str) -> dict:
        return {}

    def conversations_invite(self, channel: str, users: str) -> dict:
        return {}

    def auth_revoke(self) -> dict:
        return {}
    
def test_auth_callback_stores_tokens_and_me_uses_them(monkeypatch) -> None:
    # Use the in-memory store and wire it into the slack_service.app module
    store = _make_test_store()

    # Configure environment for OAuth flow + state secret
    monkeypatch.setenv("SESSION_SECRET", "state-secret")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost/callback")

    # Fake WebClient that simulates Slack's oauth_v2_access response
    class OAuthFakeWebClient:
        def __init__(self, token: str | None = None) -> None:
            self.token = token

        def oauth_v2_access(
            self,
            client_id: str,
            client_secret: str,
            code: str,
            redirect_uri: str,
        ):
            # Simulate Slack's OAuth v2 response with both user and bot tokens
            class Resp:
                def __init__(self) -> None:
                    self.data = {
                        "authed_user": {
                            "id": "U123",
                            "access_token": "user-token",
                            "refresh_token": "user-refresh",
                            "scope": "chat:write",
                        },
                        "access_token": "bot-token",
                        "scope": "channels:manage",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }

            return Resp()

    # Patch the WebClient used inside slack_service.app
    monkeypatch.setattr("slack_service.app.WebClient", OAuthFakeWebClient)

    # Build a valid state using the same secret that auth_callback will use
    state = _make_state("state-secret", ttl_sec=60)

    client = TestClient(app)

    # Hit the OAuth callback endpoint
    resp = client.get(
        "/auth/callback",
        params={"code": "dummy-code", "state": state},
        follow_redirects=False,
    )
    # Should redirect to /docs
    assert resp.status_code == 302
    assert resp.headers["location"] == "/docs"

    # The callback should have persisted both user and bot tokens
    user_bundle = store.load("U123")
    assert user_bundle is not None
    assert user_bundle.access_token == "user-token"
    assert user_bundle.refresh_token == "user-refresh"
    assert user_bundle.scope == "chat:write"

    bot_bundle = store.load("bot:U123")
    assert bot_bundle is not None
    assert bot_bundle.access_token == "bot-token"
    assert bot_bundle.scope == "channels:manage"

    # Session should now contain user_id; /me should reflect that
    me_resp = client.get("/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["ok"] is True
    assert me_data["user_id"] == "U123"
    assert me_data["has_bot_token"] is True
    assert me_data["user_scopes"] == "chat:write"
    assert me_data["bot_scopes"] == "channels:manage"


def test_logout_revokes_and_deletes_tokens(monkeypatch) -> None:
    store = _make_test_store()

    # Seed both user and bot tokens
    user_bundle = TokenBundle(
        access_token="user-token",
        refresh_token=None,
        token_type="Bearer",
        scope="chat:write",
        expires_at=None,
    )
    bot_bundle = TokenBundle(
        access_token="bot-token",
        refresh_token=None,
        token_type="Bearer",
        scope="channels:manage",
        expires_at=None,
    )
    store.save("debug-anonymous", user_bundle)
    store.save("bot:debug-anonymous", bot_bundle)

    # Avoid real Slack calls
    monkeypatch.setattr("slack_service.app.WebClient", FakeWebClient)

    client = TestClient(app)
    resp = client.delete("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Tokens should be removed from the store
    assert store.load("debug-anonymous") is None
    assert store.load("bot:debug-anonymous") is None


def test_create_channel_uses_bot_token(monkeypatch) -> None:
    store = _make_test_store()
    store.save(
        "bot:debug-anonymous",
        TokenBundle(
            access_token="bot-token",
            refresh_token=None,
            token_type="Bearer",
            scope="channels:manage",
            expires_at=None,
        ),
    )

    monkeypatch.setattr("slack_service.app.WebClient", FakeWebClient)

    client = TestClient(app)
    resp = client.post("/channels", json={"name": "team4", "is_private": False})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "C999"
    assert data["name"] == "team4"


def test_rename_channel_uses_bot_token(monkeypatch) -> None:
    store = _make_test_store()
    store.save(
        "bot:debug-anonymous",
        TokenBundle(
            access_token="bot-token",
            refresh_token=None,
            token_type="Bearer",
            scope="channels:manage",
            expires_at=None,
        ),
    )

    monkeypatch.setattr("slack_service.app.WebClient", FakeWebClient)

    client = TestClient(app)
    resp = client.patch("/channels/C123", json={"name": "renamed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "C123"
    assert data["name"] == "renamed"


def test_archive_channel_uses_bot_token(monkeypatch) -> None:
    store = _make_test_store()
    store.save(
        "bot:debug-anonymous",
        TokenBundle(
            access_token="bot-token",
            refresh_token=None,
            token_type="Bearer",
            scope="channels:manage",
            expires_at=None,
        ),
    )

    monkeypatch.setattr("slack_service.app.WebClient", FakeWebClient)

    client = TestClient(app)
    resp = client.delete("/channels/C123")
    assert resp.status_code == 204


def test_invite_members_uses_bot_token(monkeypatch) -> None:
    store = _make_test_store()
    store.save(
        "bot:debug-anonymous",
        TokenBundle(
            access_token="bot-token",
            refresh_token=None,
            token_type="Bearer",
            scope="channels:manage",
            expires_at=None,
        ),
    )

    monkeypatch.setattr("slack_service.app.WebClient", FakeWebClient)

    client = TestClient(app)
    resp = client.post(
        "/channels/C123/members",
        json={"user_ids": ["U1", "U2"]},
    )
    assert resp.status_code == 204

def test_logout_without_any_tokens_is_noop(monkeypatch) -> None:
    # Fresh in-memory store with no user/bot tokens
    store = _make_test_store()

    # Session secret for consistency with other auth flows
    monkeypatch.setenv("SESSION_SECRET", "dev-secret")

    client = TestClient(app)

    # Call logout without ever logging in or seeding tokens
    resp = client.delete("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Store should still be empty for debug-anonymous and its bot
    assert store.load("debug-anonymous") is None
    assert store.load("bot:debug-anonymous") is None


def test_create_channel_without_bot_token_forbidden(monkeypatch) -> None:
    # Fresh store: no bot token saved for this user
    _make_test_store()

    monkeypatch.setenv("SESSION_SECRET", "dev-secret")

    client = TestClient(app)

    # Call /channels without having a bot token in the store.
    response = client.post(
        "/channels",
        json={"name": "test-channel-no-bot", "is_private": False},
    )

    assert response.status_code == 403
    body = response.json()
    assert (
        body["detail"]
        == "Bot token or required scopes are missing; re-auth with app scopes."
    )

def test_debug_login_url_builds_url(monkeypatch) -> None:
    # Provide minimal OAuth env vars required by _require_oauth_env
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://example.com/callback")

    client = TestClient(app)
    resp = client.get("/__debug/login-url", params={"state": "xyz"})
    assert resp.status_code == 200

    data = resp.json()
    assert "url" in data
    url = data["url"]
    # Check key pieces are present in the built URL
    assert "client_id=cid" in url
    assert "state=xyz" in url
    assert "redirect_uri=" in url

def test_all_messages_stub_mode_returns_seeded_messages(monkeypatch) -> None:
    # Fresh store; no tokens so require_user_token returns DUMMY_TOKEN
    _make_test_store()
    monkeypatch.setenv("SESSION_SECRET", "dev-secret")

    client = TestClient(app)
    resp = client.get("/messages")
    assert resp.status_code == 200

    data = resp.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)
    # In stub mode there should be at least one seeded message
    assert len(data["messages"]) >= 1
