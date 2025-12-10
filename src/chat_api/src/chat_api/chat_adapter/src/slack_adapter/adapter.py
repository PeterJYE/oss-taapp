"""Slack adapter: typed, ruff/mypy-clean, and test-friendly.

This module provides two adapter variants used by your tests:

1) ServiceAdapter
   - Lightweight wrapper around a provided HTTPX-like client factory.
   - Used by coverage tests: ServiceAdapter(lambda: http_stub)

2) ServiceBackedClient / SlackServiceBackedClient
   - Higher-level client that can either:
       a) Use an injected "generated client" via ``._client`` that exposes
          ``get_httpx_client()``, or
       b) Fall back to a provided HTTP client from ``base_url``.
   - Exposes ``health()``, ``list_channels()``, ``post_message()``, context mgmt, etc.

Both variants depend only on a minimal HTTP shape:
- ``request(method, url, *, params, json, headers, timeout) -> resp`` with
  ``.status_code`` and ``.json()`` attributes.

They also map service JSON to the shared ``slack_api`` dataclasses:
- ``Channel(...)``
- ``Message(...)``
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol, Self, cast, runtime_checkable

if TYPE_CHECKING:
    from types import TracebackType

# We rely on the shared API models from your project.
from slack_api import Channel, Message


@runtime_checkable
class _HTTPResponseLike(Protocol):
    """Minimal response protocol expected from the HTTP client."""

    status_code: int

    def json(self) -> object:
        """Return the decoded JSON payload."""
        ...


@runtime_checkable
class _HTTPClientLike(Protocol):
    """Minimal HTTPX-like client interface we rely on."""

    def request(  # noqa: PLR0913
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _HTTPResponseLike:
        ...

    def close(self) -> None:
        """Close underlying transport."""
        ...


# -----------------------
# Helper and parsing utils
# -----------------------


def _get_id(obj: object) -> str:
    """Extract a generic 'id' from known Slack message/channel shapes.

    Supports both mapping-like objects and model instances with attributes
    such as ``id``, ``message_id``, or ``ts``.
    """
    if isinstance(obj, Mapping):
        raw = obj.get("id") or obj.get("message_id") or obj.get("ts") or ""
        return str(raw)

    # Attribute-based fallback (for dataclass / pydantic models, etc.).
    for attr in ("id", "message_id", "ts"):
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if value is not None:
                return str(value)

    return ""


def _as_channel(item: Mapping[str, object]) -> Channel:
    """Convert a raw dict into a Channel model."""
    cid = str(item.get("id", ""))
    name = str(item.get("name", ""))
    # Channel dataclass is simple and stable.
    return Channel(id=cid, name=name)


def _as_message(item: Mapping[str, object]) -> Message:
    """Convert a raw dict to Message, with safe defaults.

    We purposefully avoid relying on a single exact constructor signature.
    Instead, we try the most descriptive keyword-based call first and
    gracefully fall back to simpler variants if needed.
    """
    mid = str(item.get("id", "")) or str(item.get("message_id", "")) or str(
        item.get("ts", ""),
    )
    text = str(item.get("text", ""))
    channel_id = str(item.get("channel_id", ""))
    ts_val = item.get("ts")
    ts = str(ts_val) if ts_val is not None else None

    # Preferred: constructor that accepts message_id + channel_id + ts.
    try:
        return Message(
            message_id=mid,
            text=text,
            channel_id=channel_id,
            ts=ts,
        )
    except TypeError as first_error:
        # Fallback: constructor that accepts text/channel_id[/ts].
        try:
            return Message(
                text=text,
                channel_id=channel_id,
                ts=ts,
            )
        except TypeError:
            try:
                return Message(
                    text=text,
                    channel_id=channel_id,
                )
            except TypeError:
                # If all constructor shapes fail, surface the first error.
                raise first_error from None


def _health_from_json(data: Mapping[str, object]) -> bool:
    """Heuristically decide service health from varied JSON shapes."""
    ok_val = data.get("ok")
    if isinstance(ok_val, bool):
        return ok_val
    status = data.get("status")
    if isinstance(status, int):
        return status == int(HTTPStatus.OK)
    if isinstance(status, str):
        return status.lower() in {"ok", "healthy", "up"}
    # Fallback: non-empty JSON and no explicit "error" -> assume OK
    if data:
        return not any(k in data for k in ("error", "errors", "detail"))
    return True


# -----------------------
# Base client with factory
# -----------------------


@dataclass
class ServiceBackedClient:
    """HTTP client wrapper with simple Slack-like service calls."""

    base_url: str = ""
    http: _HTTPClientLike | None = None

    # -------------- lifecycle --------------

    def __enter__(self) -> Self:
        """Enter context manager and return self."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client, if any."""
        self.close()

    def close(self) -> None:
        """Explicitly close the underlying HTTP client, if present."""
        if self.http is not None:
            close_fn = getattr(self.http, "close", None)
            if callable(close_fn):
                close_fn()

    # -------------- internal helpers --------------

    def _get_http_client(self) -> _HTTPClientLike:
        """Return the HTTP client or raise if missing."""
        if self.http is None:
            message = "HTTP client not configured"
            raise RuntimeError(message)
        return self.http

    def _make_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}" if self.base_url else path

    def _do_request(  # noqa: PLR0913
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _HTTPResponseLike:
        """Issue a request using the configured HTTP client."""
        client = self._get_http_client()
        url = self._make_url(path)
        return client.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=timeout,
        )

    # -------------- high-level API --------------

    def message_identifier(self, obj: object) -> str:
        """Return a stable identifier for a message or mapping-like object.

        Raises
        ------
            ValueError: If no suitable identifier can be derived from ``obj``.

        """
        identifier = _get_id(obj)
        if not identifier:
            message = "Object does not contain a usable identifier"
            raise ValueError(message)
        return identifier

    def health(self) -> bool:
        """Return True when the service reports a healthy /health response."""
        try:
            resp = self._do_request("GET", "/health")
        except (OSError, RuntimeError):
            return False
        if resp.status_code >= int(HTTPStatus.INTERNAL_SERVER_ERROR):
            return False
        try:
            data = resp.json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            return resp.status_code == int(HTTPStatus.OK)
        if not isinstance(data, Mapping):
            return resp.status_code == int(HTTPStatus.OK)
        return _health_from_json(data)

    def list_channels(self) -> list[Channel]:
        """Fetch channels and map to Channel models."""
        resp = self._do_request("GET", "/channels")
        try:
            data = resp.json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            raw: object = data
        elif isinstance(data, Mapping):
            raw = data.get("channels", [])
        else:
            return []
        if not isinstance(raw, list):
            return []
        return [_as_channel(it) for it in raw if isinstance(it, Mapping)]

    def post_message(self, channel_id: str, text: str) -> Message:
        """Post a message and return the resulting Message model."""
        payload: dict[str, object] = {"channel_id": channel_id, "text": text}
        resp = self._do_request(
            "POST",
            f"/channels/{channel_id}/messages",
            json=payload,
        )
        try:
            data = resp.json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            # Minimal fallback if no JSON
            return _as_message({"id": "", "channel_id": channel_id, "text": text})
        raw = data.get("message") if isinstance(data, Mapping) else None
        if isinstance(raw, Mapping):
            return _as_message(raw)
        return _as_message({"id": "", "channel_id": channel_id, "text": text})


# -----------------------------------------------------
# ServiceAdapter: wraps a factory that yields HTTP client
# -----------------------------------------------------


class ServiceAdapter:
    """Factory-based adapter used heavily in tests.

    The factory is expected to return an HTTPX-like client. We support:
    - A generic ``request(...)`` method, or
    - ``get(...)`` / ``post(...)`` only clients (for coverage tests).
    """

    def __init__(self, factory: Callable[[], object], base_url: str = "") -> None:
        self._factory = factory
        self._base_url = base_url.rstrip("/")
        self._client_obj: object | None = None

    # internal helpers

    def _ensure(self) -> object:
        if self._client_obj is None:
            self._client_obj = self._factory()
        return self._client_obj

    def close(self) -> None:
        """Close the underlying HTTP client, if it exposes ``close()``."""
        cli = self._client_obj
        if cli is not None:
            close_fn = getattr(cli, "close", None)
            if callable(close_fn):
                close_fn()

    # public API mirrors ServiceBackedClient

    def _make_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not self._base_url:
            return path
        return f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"

    def _do_request(  # noqa: PLR0913
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _HTTPResponseLike:
        """Issue an HTTP request using the created client.

        Supports either ``request(...)`` or only ``get/post`` style clients.
        Any incompatible client results in a wrapped ``RuntimeError`` so that
        callers can uniformly treat health() as False in this scenario.
        """
        cli = self._ensure()
        url = self._make_url(path)
        message_no_methods = "HTTP client lacks request/get/post methods"

        def _raise_incompatible() -> None:
            raise AttributeError(message_no_methods)

        try:
            request_fn = getattr(cli, "request", None)
            if callable(request_fn):
                return cast(
                    "_HTTPResponseLike",
                    request_fn(
                        method,
                        url,
                        params=params,
                        json=json,
                        headers=headers,
                        timeout=timeout,
                    ),
                )
            # Fallback: GET/POST-only style client.
            method_upper = method.upper()
            if method_upper == "GET":
                get_fn = getattr(cli, "get", None)
                if callable(get_fn):
                    return cast(
                        "_HTTPResponseLike",
                        get_fn(
                            url,
                            params=params,
                            headers=headers,
                            timeout=timeout,
                        ),
                    )
            if method_upper == "POST":
                post_fn = getattr(cli, "post", None)
                if callable(post_fn):
                    return cast(
                        "_HTTPResponseLike",
                        post_fn(
                            url,
                            json=json,
                            headers=headers,
                            timeout=timeout,
                        ),
                    )
            # If we reach here, the client is not compatible.
            _raise_incompatible()
        except AttributeError as exc:
            message_incompatible = f"Incompatible HTTP client: {exc}"
            raise RuntimeError(message_incompatible) from exc

        # This line should be unreachable but satisfies the type checker.
        unreachable_message = "Unreachable path in ServiceAdapter._do_request"
        raise RuntimeError(unreachable_message)


    # High-level API

    def health(self) -> bool:
        """Return True when the backing service reports a healthy /health."""
        try:
            resp = self._do_request("GET", "/health")
        except (OSError, RuntimeError):
            return False
        if resp.status_code >= int(HTTPStatus.INTERNAL_SERVER_ERROR):
            return False
        try:
            data = resp.json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            return resp.status_code == int(HTTPStatus.OK)
        if not isinstance(data, Mapping):
            return resp.status_code == int(HTTPStatus.OK)
        return _health_from_json(data)

    def list_channels(self) -> list[Channel]:
        """Fetch channels from the backing service and map them to Channel."""
        resp = self._do_request("GET", "/channels")
        try:
            data = resp.json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            raw: object = data
        elif isinstance(data, Mapping):
            raw = data.get("channels", [])
        else:
            return []
        if not isinstance(raw, list):
            return []
        return [_as_channel(it) for it in raw if isinstance(it, Mapping)]

    def post_message(self, channel_id: str, text: str) -> Message:
        """Post a message via the backing service and return the Message model."""
        payload: dict[str, object] = {"channel_id": channel_id, "text": text}
        try:
            data = self._do_request(
                "POST",
                "/messages",
                json=payload,
            ).json()
        except (ValueError, AttributeError, json.JSONDecodeError):
            return _as_message({"id": "", "channel_id": channel_id, "text": text})
        raw = data.get("message") if isinstance(data, Mapping) else None
        if isinstance(raw, Mapping):
            return _as_message(raw)
        return _as_message({"id": "", "channel_id": channel_id, "text": text})

# -----------------------------------------------------
# SlackServiceBackedClient: integrates generated client
# -----------------------------------------------------


class SlackServiceBackedClient(ServiceBackedClient):
    """Slack service client that understands a generated Slack API client.

    Tests may inject a generated client instance into ``adapter._client`` which
    exposes ``get_httpx_client() -> httpx.Client``. When present, that client
    is used; otherwise, we fall back to the base ``http`` client.
    """

    # This attribute is test-only; kept as ``object`` for maximal flexibility.
    _client: object | None

    def __init__(self, base_url: str = "", http: _HTTPClientLike | None = None) -> None:
        super().__init__(base_url=base_url, http=http)
        self._client = None

    def _get_http_client(self) -> _HTTPClientLike:
        # If tests injected a generated client, try to obtain its httpx client.
        if self._client is not None:
            gen = self._client
            get_httpx = getattr(gen, "get_httpx_client", None)
            if callable(get_httpx):
                return cast("_HTTPClientLike", get_httpx())
            # Fallback: if it already behaves like an HTTP client, use it.
            if isinstance(gen, _HTTPClientLike):
                return gen
        # Otherwise, default to the normal behaviour.
        return super()._get_http_client()


    def close(self) -> None:
        """Close the underlying HTTP client, including generated clients."""
        # Prefer the generated client if present.
        if self._client is not None:
            gen = self._client
            get_httpx = getattr(gen, "get_httpx_client", None)
            if callable(get_httpx):
                http_client = get_httpx()
                close_fn = getattr(http_client, "close", None)
                if callable(close_fn):
                    close_fn()
                    return
            if isinstance(gen, _HTTPClientLike):
                close_fn = getattr(gen, "close", None)
                if callable(close_fn):
                    close_fn()
                    return

        # Fallback: close the base HTTP client, if any.
        super().close()

