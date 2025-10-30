"""Simple AI service adapter implementation.

This adapter exposes a small synchronous API (generate, chat, health_check)
and forwards calls to a provided generated-client instance or to an HTTP
service at ``base_url`` using httpx. The code keeps the surface small so it is
easy to wire into tests and the rest of the project.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

import httpx

if TYPE_CHECKING:
    # collections.abc.Mapping is only required for type-checking annotations
    from collections.abc import Mapping


HTTP_OK = 200
HTTP_BAD = 400


class AdapterError(Exception):
    """Base adapter exception."""


class AdapterNetworkError(AdapterError):
    """Network-level error communicating with the remote service."""


class AdapterAPIError(AdapterError):
    def __init__(self, status_code: int, content: bytes | str | None = None) -> None:
        # Content may be bytes; convert to a safe string representation.
        content_repr = repr(content) if isinstance(content, bytes) else str(content)
        message = f"API error {status_code}: {content_repr}"
        super().__init__(message)
        self.status_code = status_code
        self.content = content


class GeneratedClientProtocol(Protocol):
    def generate(self, payload: Mapping[str, object]) -> object:  # pragma: no cover - typing only
        ...

    def chat(self, payload: Mapping[str, object]) -> object:  # pragma: no cover - typing only
        ...

    def health(self) -> object | None:  # pragma: no cover - typing only
        ...


def _resp_to_text(resp: object) -> str:
    """Convert a response-like object to text safely.

    Handles objects with a ``text`` attribute, dict-like results, and
    falls back to ``str(resp)``.
    """
    if hasattr(resp, "text"):
        return str(resp.text)  # type: ignore[attr-defined]
    if isinstance(resp, dict):
        return str(resp.get("text", ""))
    return str(resp)


class AIAdapter:
    """Adapter that implements a small AI client surface and forwards calls.

    The constructor accepts either a generated-client instance (client) or a
    ``base_url`` to target a running service. If both are provided, ``client``
    is preferred.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: GeneratedClientProtocol | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._provided_client = client
        self._base_url = base_url
        self._timeout = timeout

        # If no generated client is provided, create a simple httpx client
        if client is None:
            if not base_url:
                msg = "Either 'client' or 'base_url' must be provided"
                raise ValueError(msg)
            self._http: httpx.Client | None = httpx.Client(base_url=base_url, timeout=timeout)
        else:
            self._http = None

    # --- helpers to adapt various generated-client shapes ---
    def _call_client_method(self, method_name: str, *args: object, **kwargs: object) -> object:
        """Call an appropriate method on the provided generated client.

        Some generated clients expose methods directly (e.g. ``generate``),
        others nest API groups (e.g. ``client.ai.generate``). This helper
        tries a small set of heuristics to find and call the right callable.
        """
        client = self._provided_client
        if client is None:
            msg = "No generated client provided"
            raise AdapterError(msg)

        # Direct method first
        if hasattr(client, method_name):
            return getattr(client, method_name)(*args, **kwargs)

        # Some generated clients group endpoints by resource (e.g. client.ai.generate)
        for attr in ("ai", "model", "default", "client"):
            if hasattr(client, attr):
                group = getattr(client, attr)
                if hasattr(group, method_name):
                    method = getattr(group, method_name)
                    return method(*args, **(kwargs or {}))

        # Some clients provide a low-level request method: try a simple POST helper
        # We attempt to detect common names like post or request and fall back to them.
        if hasattr(client, "post"):
            post = client.post  # type: ignore[attr-defined]
            payload = (kwargs or {}).get("json") or (args[0] if args else None)
            return post(f"/{method_name}", json=payload)
        if hasattr(client, "request"):
            request = client.request  # type: ignore[attr-defined]
            payload = (kwargs or {}).get("json") or (args[0] if args else None)
            return request("POST", f"/{method_name}", json=payload)

        msg = f"Provided generated-client does not expose {method_name}"
        raise AdapterError(msg)

    # --- public API ---
    def generate(self, prompt: str, *, max_tokens: int = 256) -> str:
        """Call the model to synchronously generate text for ``prompt``.

        Returns the generated text on success or raises :class:`AdapterError` on
        failure.
        """
        payload: dict[str, object] = {"prompt": prompt, "max_tokens": max_tokens}

        try:
            if self._provided_client is not None:
                resp = self._call_client_method("generate", payload)
                return _resp_to_text(resp)

            assert self._http is not None
            r = self._http.post("/generate", json=payload)
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        except AdapterError:
            raise
        except Exception as exc:  # pragma: no cover - unexpected client error
            raise AdapterError(exc) from exc

        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)

        body = r.json()
        return str(body.get("text", ""))

    def chat(self, messages: list[dict[str, object]]) -> str:
        """Send a conversation-style request with ``messages`` and return text.

        Each message should be a mapping with at least ``{"role": ..., "content": ...}``.
        """
        payload = {"messages": messages}

        try:
            if self._provided_client is not None:
                resp = self._call_client_method("chat", payload)
                return _resp_to_text(resp)

            assert self._http is not None
            r = self._http.post("/chat", json=payload)
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        except AdapterError:
            raise
        except Exception as exc:  # pragma: no cover - unexpected client error
            raise AdapterError(exc) from exc

        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)

        return str(r.json().get("text", ""))

    def health_check(self) -> bool:
        """Return ``True`` if the remote service responds healthy.

        Prefer a generated client's health endpoint if available; otherwise
        perform an HTTP GET to ``/health``.
        """
        try:
            if self._provided_client is not None:
                # try health on client or grouped API
                try:
                    resp = self._call_client_method("health")
                except AdapterError:
                    return True

                if resp is None:
                    return True
                return bool(getattr(resp, "ok", True))

            assert self._http is not None
            r = self._http.get("/health")
        except httpx.HTTPError:
            return False
        else:
            return r.status_code == HTTP_OK
