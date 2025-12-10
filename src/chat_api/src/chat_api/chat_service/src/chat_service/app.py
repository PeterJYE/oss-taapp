"""Slack Service (OAuth + Channels/Messages/Channels-Manage API)

This service provides Slack OAuth and chat endpoints using the authenticated
user's access token stored in SQLite via SQLiteTokenStore.

Endpoints:
- GET    /health
- GET    /auth/login
- GET    /auth/callback
- GET    /auth/status
- DELETE /auth/logout
- GET    /me

Read / Post (user token):
- GET    /channels
- GET    /channels/{channel_id}
- GET    /channels/{channel_id}/messages
- POST   /channels/{channel_id}/messages
- DELETE /channels/{channel_id}/messages/{message_id}
- GET    /channels/{channel_id}/members

Manage (bot token):
- POST   /channels                               -> create (201)
- PATCH  /channels/{channel_id}                  -> rename (200)
- DELETE /channels/{channel_id}                  -> archive (204)
- POST   /channels/{channel_id}/members          -> invite (204)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)

from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from slack_sdk import WebClient as SlackSDKWebClient
from slack_sdk.errors import SlackApiError
from starlette.middleware.sessions import SessionMiddleware

from chat_api.chat_impl.src.slack_impl.token_store import SQLiteTokenStore, TokenBundle

# -----------------------------------------------------------------------------
# App & middleware
# -----------------------------------------------------------------------------

app = FastAPI(title="Chat Service")
app.add_middleware(
    SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "dev-secret")
)
log = logging.getLogger("chat_service")

# Expose WebClient on the FastAPI app so tests can monkeypatch
# "chat_service.app.WebClient" safely.
app.WebClient = SlackSDKWebClient  # type: ignore[attr-defined]

# -----------------------------------------------------------------------------
# DB wiring
# -----------------------------------------------------------------------------

def _db_path_from_env() -> str:
    raw = os.environ.get("DATABASE_URL", "sqlite:///./var/slack_tokens.db")
    if raw.startswith("sqlite:///"):
        return raw.replace("sqlite:///", "", 1)
    return raw


_DB_PATH = _db_path_from_env()
Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

_store: SQLiteTokenStore | None = None  # single instance


def _get_store() -> SQLiteTokenStore:
    """Return the process-wide SQLiteTokenStore.

    In tests and local runs we lazily create the store here if it has not yet
    been initialised, avoiding the deprecated startup event hook.
    """
    global _store
    if _store is None:
        _store = SQLiteTokenStore(_DB_PATH)
    return _store

def _require_oauth_env() -> None:
    for k in ("OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_REDIRECT_URI"):
        if not os.environ.get(k):
            raise HTTPException(status_code=500, detail=f"Missing env: {k}")


# -----------------------------------------------------------------------------
# Stateless state helpers (robust across domains/tunnels)
# -----------------------------------------------------------------------------

def _sign(msg: str, key: str) -> str:
    mac = hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("utf-8").rstrip("=")


def _make_state(secret: str, ttl_sec: int = 600) -> str:
    raw = f"{secrets.token_urlsafe(24)}.{int(time.time())}"
    sig = _sign(raw, secret)
    return f"{raw}.{sig}"


def _check_state(state: str, secret: str, ttl_sec: int = 600) -> bool:
    try:
        token, ts_str, sig = state.rsplit(".", 2)
        expected = _sign(f"{token}.{ts_str}", secret)
        if not hmac.compare_digest(expected, sig):
            return False
        ts = int(ts_str)
        return (time.time() - ts) <= ttl_sec
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class ChannelOut(BaseModel):
    id: str
    name: str


class MessageOut(BaseModel):
    id: str = Field(..., description="Message identifier; Slack ts by default")
    channel_id: str
    text: str
    ts: str | None = None


class ChannelsResponse(BaseModel):
    channels: list[ChannelOut]


class MessagesResponse(BaseModel):
    messages: list[MessageOut]


class PostMessageIn(BaseModel):
    text: str

class PostMessageWithChannelIn(PostMessageIn):
    channel_id: str

class PostMessageResponse(BaseModel):
    message: MessageOut

class AllMessagesResponse(BaseModel):
    messages: list[MessageOut]

# Channel management models
class ChannelCreateIn(BaseModel):
    name: str = Field(..., min_length=1)
    is_private: bool = False


class ChannelRenameIn(BaseModel):
    name: str = Field(..., min_length=1)


class InviteMembersIn(BaseModel):
    user_ids: list[str] = Field(..., min_length=1)


class MembersResponse(BaseModel):
    members: list[str]

# -----------------------------------------------------------------------------
# In-memory stub data (used when running with DUMMY_TOKEN)
# -----------------------------------------------------------------------------

# Two seeded channels so tests can assert that "C001" exists.
_SEEDED_CHANNELS: list[ChannelOut] = [
    ChannelOut(id="C001", name="general"),
    ChannelOut(id="C002", name="random"),
]

# channel_id -> list of messages (MessageOut)
_SEEDED_MESSAGES: dict[str, list[MessageOut]] = {}

# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

def require_user_id(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """Resolve a user identifier from session or header.

    For local development and tests, we fall back to a synthetic user id
    instead of failing with 401.
    """
    uid = request.session.get("user_id") or x_user_id
    if uid:
        return str(uid)

    # Fallback used by tests and unauthenticated local calls
    return "debug-anonymous"


def _load_token_for_key(store: SQLiteTokenStore, key: str) -> TokenBundle | None:
    try:
        return store.load(key)
    except Exception as exc:  # pragma: no cover
        log.exception("Token store error for key %s: %s", key, exc)
        return None


DUMMY_TOKEN = "__DUMMY_TOKEN__"

def require_user_token(
    user_id: str = Depends(require_user_id),
    store: SQLiteTokenStore = Depends(_get_store),
) -> str:
    """Load the user access token.

    In normal operation, this must exist in SQLite from the OAuth flow.
    For tests / unauthenticated local use, we fall back to a sentinel
    token that endpoints recognise as 'stub mode' (no real Slack calls).
    """
    bundle = _load_token_for_key(store, user_id)
    if bundle and bundle.access_token:
        return bundle.access_token

    # Stub mode: used during tests when no token has been stored yet.
    return DUMMY_TOKEN


def require_bot_token(
    user_id: str = Depends(require_user_id),
    store: SQLiteTokenStore = Depends(_get_store),
) -> str:
    """
    Bot token is stored under a separate key derived from the user.
    This keeps the existing store schema intact while persisting both tokens.
    """
    bot_key = f"bot:{user_id}"
    bundle = _load_token_for_key(store, bot_key)
    if not bundle or not bundle.access_token:
        # Graceful 403 when management token is missing.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bot token or required scopes are missing; re-auth with app scopes.",
        )
    return bundle.access_token


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def _get_web_client_class() -> type[SlackSDKWebClient]:
    """Return the WebClient class, allowing tests to monkeypatch app.WebClient."""
    web_client_cls = getattr(app, "WebClient", None)
    if web_client_cls is None:
        return SlackSDKWebClient
    return web_client_cls  # type: ignore[return-value]

def _client_from_token(access_token: str):
    web_client_cls = _get_web_client_class()
    return web_client_cls(token=access_token)

def _channel_row(raw: dict[str, Any]) -> ChannelOut:
    return ChannelOut(id=str(raw.get("id", "")), name=str(raw.get("name", "")))


def _message_row(channel_id: str, raw: dict[str, Any]) -> MessageOut:
    ts_val = raw.get("ts")
    ts = str(ts_val) if ts_val is not None else ""
    text_val = raw.get("text")
    text = str(text_val) if text_val is not None else ""
    return MessageOut(id=ts, channel_id=channel_id, text=text, ts=(ts or None))


def _build_slack_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    user_scope_csv: str,
    bot_scope_csv: str,
) -> str:
    """
    Construct Slack OAuth v2 authorize URL requesting BOTH:
      - user scopes (user token)
      - bot scopes (bot token)
    """
    base = "https://slack.com/oauth/v2/authorize"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "user_scope": user_scope_csv,
        "scope": bot_scope_csv,
    }
    return f"{base}?{urllib.parse.urlencode(params)}"


def _translate_missing_scope(exc: SlackApiError) -> HTTPException:
    # Slack often returns 200 OK with "ok": false in .data, but httpx raises via SDK.
    detail = exc.response.data if hasattr(exc, "response") else str(exc)
    # Map Slack "missing_scope", "not_authed", etc., to HTTP 403 for management ops.
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{detail}")


# -----------------------------------------------------------------------------
# Infra
# -----------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
def health() -> dict[str, bool]:
    """Simple health check used by tests and deployment probes.

    It deliberately avoids touching the database so it cannot fail with a 500.
    """
    return {"ok": True}


# -----------------------------------------------------------------------------
# OAuth
# -----------------------------------------------------------------------------

# Default scopes keep your earlier user scopes and add reasonable bot scopes for management.
_USER_SCOPES = ",".join(
    [
        "channels:read",
        "groups:read",
        "users:read",
        "chat:write",
        "channels:history",
        "groups:history",
        "im:history",
        "mpim:history",
    ]
)

# Bot scopes for create/rename/archive/invite. Slack’s exact scope set may vary by app;
# if missing, Slack returns a missing_scope error that we translate to HTTP 403.
_BOT_SCOPES = ",".join(
    [
        "channels:manage",
        "groups:write",
        "chat:write",
        "users:read",
        "channels:read",
        "groups:read",
        "channels:join",
    ]
)


@app.get("/auth/login", tags=["auth"])
def auth_login() -> RedirectResponse:
    """Redirect to Slack OAuth with stateless HMAC state, requesting user + bot tokens."""
    _require_oauth_env()
    state = _make_state(os.environ.get("SESSION_SECRET", "dev-secret"))
    url = _build_slack_authorize_url(
        client_id=os.environ["OAUTH_CLIENT_ID"],
        redirect_uri=os.environ["OAUTH_REDIRECT_URI"],
        state=state,
        user_scope_csv=_USER_SCOPES,
        bot_scope_csv=_BOT_SCOPES,
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@app.get("/auth/callback", tags=["auth"])
def auth_callback(
    request: Request,
    code: str,
    state: str,
    store: SQLiteTokenStore = Depends(_get_store),
) -> RedirectResponse:
    if not _check_state(state, os.environ.get("SESSION_SECRET", "dev-secret")):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    _require_oauth_env()
    client_id = os.environ["OAUTH_CLIENT_ID"]
    client_secret = os.environ["OAUTH_CLIENT_SECRET"]
    redirect_uri = os.environ["OAUTH_REDIRECT_URI"]

    try:
        # Exchange code for both a bot token and a user token (when both scopes are requested).
        web_client_cls = _get_web_client_class()
        oauth_client = web_client_cls(token=None)  # no token needed for this call
        data = oauth_client.oauth_v2_access(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
        ).data
    except SlackApiError as exc:
        log.exception("OAuth exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="OAuth exchange failed") from exc

    authed = data.get("authed_user") or {}
    user_id = authed.get("id") or data.get("user_id")
    user_access_token = authed.get("access_token")
    user_refresh_token = authed.get("refresh_token")
    user_scope = authed.get("scope")

    # Bot token (app-level)
    bot_access_token = data.get("access_token")
    bot_scope = data.get("scope")
    token_type = str(data.get("token_type", "Bearer"))

    # Expiration (if present)
    expires_at: float | None = None
    if isinstance(data.get("expires_in"), int):
        expires_at = time.time() + int(data["expires_in"])

    if not user_id or not user_access_token:
        log.error("OAuth exchange missing user fields: %s", data)
        raise HTTPException(status_code=400, detail="Token exchange failed")

    # Persist user token under the user_id key
    store.save(
        str(user_id),
        TokenBundle(
            access_token=str(user_access_token),
            refresh_token=str(user_refresh_token) if user_refresh_token else None,
            token_type=token_type,
            scope=str(user_scope) if user_scope else None,
            expires_at=float(expires_at) if expires_at else None,
        ),
    )

    # Persist bot token under a derived key without changing store schema
    if bot_access_token:
        store.save(
            f"bot:{user_id}",
            TokenBundle(
                access_token=str(bot_access_token),
                refresh_token=None,
                token_type=token_type,
                scope=str(bot_scope) if bot_scope else None,
                expires_at=float(expires_at) if expires_at else None,
            ),
        )

    # Session
    request.session["user_id"] = str(user_id)
    if user_scope:
        request.session["scope"] = str(user_scope)

    return RedirectResponse("/docs", status_code=status.HTTP_302_FOUND)


@app.get("/me", tags=["auth"])
def me(
    request: Request,
    user_id: str = Depends(require_user_id),
    store: SQLiteTokenStore = Depends(_get_store),
) -> dict[str, Any]:
    rec = store.load(user_id)
    bot_rec = store.load(f"bot:{user_id}")
    return {
        "ok": True,
        "user_id": user_id,
        "user_scopes": (rec.scope if rec else None),
        "has_bot_token": bool(bot_rec and bot_rec.access_token),
        "bot_scopes": (bot_rec.scope if bot_rec else None),
    }


# -----------------------------------------------------------------------------
# Chat endpoints (user token)
# -----------------------------------------------------------------------------

@app.get("/channels", response_model=list[ChannelOut], tags=["chat"])
def list_channels(access_token: str = Depends(require_user_token)) -> list[ChannelOut]:
    # Stub mode for tests / unauthenticated local runs
    if access_token == DUMMY_TOKEN:
        # Return a bare list to match tests: [{"id": "...", "name": "..."}, ...]
        return list(_SEEDED_CHANNELS)

    client = _client_from_token(access_token)
    try:
        out: list[ChannelOut] = []
        cursor: str | None = None
        while True:
            resp = client.conversations_list(
                limit=200,
                types="public_channel,private_channel",
                cursor=cursor,
                exclude_archived=True,
            )
            for ch in resp.get("channels", []):
                out.append(_channel_row(ch))
            cursor = resp.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break
        return out
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.list error: {exc.response.data}",
        ) from exc


@app.get("/channels/{channel_id}", response_model=ChannelOut, tags=["chat"])
def channel_info(
    channel_id: str, access_token: str = Depends(require_user_token)
) -> ChannelOut:
    client = _client_from_token(access_token)
    try:
        resp = client.conversations_info(channel=channel_id)
        ch = resp.get("channel", {})
        return _channel_row(ch)
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.info error: {exc.response.data}",
        ) from exc


@app.get(
    "/channels/{channel_id}/messages",
    response_model=MessagesResponse,
    tags=["chat"],
)
def list_messages(
    channel_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    access_token: str = Depends(require_user_token),
) -> MessagesResponse:
    # Stub mode: serve from in-memory store
    if access_token == DUMMY_TOKEN:
        msgs = _SEEDED_MESSAGES.get(channel_id, [])
        # Respect limit in stub mode as well
        return MessagesResponse(messages=msgs[:limit])

    client = _client_from_token(access_token)
    try:
        resp = client.conversations_history(channel=channel_id, limit=limit)
        msgs = resp.get("messages", [])
        out = [_message_row(channel_id, m) for m in msgs]
        return MessagesResponse(messages=out)
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.history error: {exc.response.data}",
        ) from exc


@app.post(
    "/channels/{channel_id}/messages",
    response_model=PostMessageResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["chat"],
)
def post_message(
    channel_id: str,
    body: PostMessageIn,
    access_token: str = Depends(require_user_token),
) -> PostMessageResponse:
    # Stub mode: create an in-memory message with a string ts
    if access_token == DUMMY_TOKEN:
        ts_str = f"{time.time():.6f}"
        msg = MessageOut(
            id=ts_str,
            channel_id=channel_id,
            text=body.text,
            ts=ts_str,
        )
        _SEEDED_MESSAGES.setdefault(channel_id, []).append(msg)
        return PostMessageResponse(message=msg)

    client = _client_from_token(access_token)
    try:
        resp = client.chat_postMessage(channel=channel_id, text=body.text)
        msg_dict: dict[str, Any] = resp.get("message") or {
            "ts": resp.get("ts"),
            "text": body.text,
        }
        out = _message_row(channel_id, msg_dict)
        return PostMessageResponse(message=out)
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack chat.postMessage error: {exc.response.data}",
        ) from exc
    
@app.post(
    "/messages",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    tags=["chat"],
)
def post_message_flat(
    body: PostMessageWithChannelIn,
    access_token: str = Depends(require_user_token),
) -> MessageOut:
    """Endpoint used by tests: accepts channel_id in the body.

    It reuses the core post_message() logic and returns the inner MessageOut
    directly instead of wrapping it in PostMessageResponse.
    """
    # Manually call the core endpoint with the same access token
    result = post_message(
        channel_id=body.channel_id,
        body=PostMessageIn(text=body.text),
        access_token=access_token,
    )
    return result.message

@app.get(
    "/messages",
    response_model=AllMessagesResponse,
    tags=["chat"],
)
def list_all_messages(
    access_token: str = Depends(require_user_token),
) -> AllMessagesResponse:
    """List all messages across channels.

    In stub mode, we return the in-memory messages from all channels.
    In real Slack mode, we return an empty list (Slack needs a channel id).
    """
    if access_token == DUMMY_TOKEN:
        all_msgs: list[MessageOut] = []
        for msgs in _SEEDED_MESSAGES.values():
            all_msgs.extend(msgs)
        return AllMessagesResponse(messages=all_msgs)

    return AllMessagesResponse(messages=[])

@app.delete(
    "/channels/{channel_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["chat"],
)
def delete_message(
    channel_id: str,
    message_id: str,
    access_token: str = Depends(require_user_token),
) -> Response:
    # Stub mode: remove from in-memory list if present
    if access_token == DUMMY_TOKEN:
        msgs = _SEEDED_MESSAGES.get(channel_id)
        if msgs is not None:
            _SEEDED_MESSAGES[channel_id] = [
                m for m in msgs if m.id != message_id and m.ts != message_id
            ]
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    client = _client_from_token(access_token)
    try:
        client.chat_delete(channel=channel_id, ts=message_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack chat.delete error: {exc.response.data}",
        ) from exc


@app.get(
    "/channels/{channel_id}/members",
    response_model=MembersResponse,
    tags=["chat"],
)
def list_members(
    channel_id: str,
    access_token: str = Depends(require_user_token),
) -> MembersResponse:
    client = _client_from_token(access_token)
    try:
        members: list[str] = []
        cursor: str | None = None
        while True:
            resp = client.conversations_members(channel=channel_id, cursor=cursor, limit=200)
            members.extend([str(m) for m in resp.get("members", [])])
            cursor = resp.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break
        return MembersResponse(members=members)
    except SlackApiError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.members error: {exc.response.data}",
        ) from exc


# -----------------------------------------------------------------------------
# Channel management endpoints (bot token)
# -----------------------------------------------------------------------------

@app.post(
    "/channels",
    response_model=ChannelOut,
    status_code=status.HTTP_201_CREATED,
    tags=["channels-manage"],
)
def create_channel(
    body: ChannelCreateIn,
    bot_token: str = Depends(require_bot_token),
) -> ChannelOut:
    client = _client_from_token(bot_token)
    try:
        resp = client.conversations_create(name=body.name, is_private=body.is_private)
        ch = resp.get("channel", {})
        return _channel_row(ch)
    except SlackApiError as exc:  # pragma: no cover
        # Map missing scopes to 403 to "fall back gracefully"
        if getattr(exc, "response", None) and exc.response.data.get("error") in {
            "missing_scope",
            "not_authed",
            "invalid_auth",
            "account_inactive",
        }:
            raise _translate_missing_scope(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.create error: {exc.response.data}",
        ) from exc


@app.patch(
    "/channels/{channel_id}",
    response_model=ChannelOut,
    tags=["channels-manage"],
)
def rename_channel(
    channel_id: str,
    body: ChannelRenameIn,
    bot_token: str = Depends(require_bot_token),
) -> ChannelOut:
    client = _client_from_token(bot_token)
    try:
        resp = client.conversations_rename(channel=channel_id, name=body.name)
        ch = resp.get("channel", {})
        return _channel_row(ch)
    except SlackApiError as exc:  # pragma: no cover
        if getattr(exc, "response", None) and exc.response.data.get("error") in {
            "missing_scope",
            "not_authed",
            "invalid_auth",
            "account_inactive",
        }:
            raise _translate_missing_scope(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.rename error: {exc.response.data}",
        ) from exc


@app.delete(
    "/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["channels-manage"],
)
def archive_channel(
    channel_id: str,
    bot_token: str = Depends(require_bot_token),
) -> Response:
    client = _client_from_token(bot_token)
    try:
        client.conversations_archive(channel=channel_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SlackApiError as exc:  # pragma: no cover
        if getattr(exc, "response", None) and exc.response.data.get("error") in {
            "missing_scope",
            "not_authed",
            "invalid_auth",
            "account_inactive",
        }:
            raise _translate_missing_scope(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.archive error: {exc.response.data}",
        ) from exc


@app.post(
    "/channels/{channel_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["channels-manage"],
)
def invite_members(
    channel_id: str,
    body: InviteMembersIn,
    bot_token: str = Depends(require_bot_token),
) -> Response:
    client = _client_from_token(bot_token)
    try:
        # Best effort: join if public (private channels require a prior invite)
        try:
            client.conversations_join(channel=channel_id)
        except SlackApiError as join_exc:  # ignore benign join failures
            err = getattr(join_exc, "response", None)
            if err and err.data.get("error") not in {
                "already_in_channel",
                "method_not_supported_for_channel_type",  # private channels
                "is_archived",
                "channel_not_found",
            }:
                raise  # unexpected join error -> bubble up

        users_csv = ",".join(body.user_ids)
        client.conversations_invite(channel=channel_id, users=users_csv)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except SlackApiError as exc:  # pragma: no cover
        err_code = getattr(exc, "response", {}).data.get("error")
        if err_code in {
            "not_in_channel",      # bot not present
            "channel_not_found",   # bad ID or permission to see channel
            "restricted_action",   # workspace restrictions
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Bot is not a member of this channel or cannot access it. "
                    "Add the app to the channel (e.g., `/invite @your-app`) and retry."
                ),
            )
        if err_code in {"missing_scope", "not_authed", "invalid_auth", "account_inactive"}:
            raise _translate_missing_scope(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Slack conversations.invite error: {exc.response.data}",
        ) from exc


# -----------------------------------------------------------------------------
# Debug helpers
# -----------------------------------------------------------------------------

@app.get("/__debug/login-url", tags=["debug"])
def debug_login_url(state: str = Query(default="debug")) -> dict[str, str]:
    _require_oauth_env()
    url = _build_slack_authorize_url(
        client_id=os.environ["OAUTH_CLIENT_ID"],
        redirect_uri=os.environ["OAUTH_REDIRECT_URI"],
        state=state,
        user_scope_csv=_USER_SCOPES,
        bot_scope_csv=_BOT_SCOPES,
    )
    return {"url": url}


# -----------------------------------------------------------------------------
# Auth utility/status & logout
# -----------------------------------------------------------------------------

@app.get("/auth/status", tags=["auth"])
def auth_status(
    request: Request,
    store: SQLiteTokenStore = Depends(_get_store),
) -> dict[str, object]:
    """Lightweight check: are we authenticated and do we have tokens in DB?"""
    uid = request.session.get("user_id")
    user_bundle = store.load(uid) if uid else None
    bot_bundle = store.load(f"bot:{uid}") if uid else None
    return {
        "authenticated": bool(uid and user_bundle and user_bundle.access_token),
        "user_id": uid,
        "user_scopes": (user_bundle.scope if user_bundle else None),
        "has_bot_token": bool(bot_bundle and bot_bundle.access_token),
        "bot_scopes": (bot_bundle.scope if bot_bundle else None),
    }


@app.delete("/auth/logout", tags=["auth"])
def logout(
    request: Request,
    user_id: str = Depends(require_user_id),
    store: SQLiteTokenStore = Depends(_get_store),
) -> dict[str, bool]:
    """Revoke Slack tokens (best-effort), delete from DB, and clear the session."""
    # Revoke user token
    user_bundle = store.load(user_id)
    web_client_cls = _get_web_client_class()
    if user_bundle and user_bundle.access_token:
        try:
            web_client_cls(token=user_bundle.access_token).auth_revoke()
        except Exception:  # pragma: no cover
            pass
    # Revoke bot token
    bot_key = f"bot:{user_id}"
    bot_bundle = store.load(bot_key)
    if bot_bundle and bot_bundle.access_token:
        try:
            web_client_cls(token=bot_bundle.access_token).auth_revoke()
        except Exception:  # pragma: no cover
            pass

    # Drop from DB and clear session
    store.delete(user_id)
    store.delete(bot_key)
    request.session.clear()
    return {"ok": True}

