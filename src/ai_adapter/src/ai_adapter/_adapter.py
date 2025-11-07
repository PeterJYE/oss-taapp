"""OpenAI Client Service adapter.

Explicit HTTP client for five endpoints, no dynamic attribute access.

Endpoints:
- POST /ai/generate-response
- POST /ai/conversations
- GET  /ai/conversations/{conversation_id}
- DELETE /ai/conversations/{conversation_id}
- GET  /health
"""
from __future__ import annotations

from typing import cast
from urllib.parse import urlparse

import httpx

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

class OpenAIServiceAdapter:
    """Concrete adapter that calls the OpenAI Client Service.

    Required headers:
    - X-Subject: the user subject required by the service for per-user data.
    """

    def __init__(self, *, base_url: str, subject: str, timeout: float = 5.0) -> None:
        if not base_url:
            msg = "base_url is required"
            raise ValueError(msg)

        self._base_url = base_url
        self._timeout = timeout
        self._headers: dict[str, str] = {"X-Subject": subject}

        transport: httpx.BaseTransport | None = None
        host = (urlparse(base_url).hostname or "").lower()
        if host == "testserver":
            try:
                from openai_client_service.main import app  # noqa: PLC0415 - lazy import for tests
                transport = cast("httpx.BaseTransport", httpx.ASGITransport(app=app))
            except ImportError:
                transport = None

        self._http = httpx.Client(base_url=base_url, headers=self._headers, timeout=timeout, transport=transport)

    def generate_response(self, messages: list[str], *, conversation_id: str | None = None) -> dict[str, object | None]:
        """POST /ai/generate-response returning content, tokens_used, conversation_id.

        Raises AdapterAPIError on non-2xx responses.
        """
        payload: dict[str, object | None] = {"messages": messages, "conversation_id": conversation_id}
        try:
            r = self._http.post("/ai/generate-response", json=payload)
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        data = r.json()
        return {
            "content": data.get("content"),
            "tokens_used": data.get("tokens_used"),
            "conversation_id": data.get("conversation_id"),
        }

    def create_conversation(self) -> str:
        """POST /ai/conversations -> returns conversation_id."""
        try:
            r = self._http.post("/ai/conversations")
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        data = r.json()
        conv_id = data.get("conversation_id")
        return str(conv_id) if conv_id is not None else ""

    def get_conversation(self, conversation_id: str) -> dict[str, object]:
        """GET /ai/conversations/{id} -> returns conversation object."""
        try:
            r = self._http.get(f"/ai/conversations/{conversation_id}")
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        return cast("dict[str, object]", r.json())

    def delete_conversation(self, conversation_id: str) -> bool:
        """DELETE /ai/conversations/{id} -> returns ok boolean in body."""
        try:
            r = self._http.delete(f"/ai/conversations/{conversation_id}")
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        body = r.json() if r.content else {"ok": True}
        ok = body.get("ok", True)
        return bool(ok)

    def health_check(self) -> bool:
        """GET /health -> bool."""
        try:
            r = self._http.get("/health")
        except httpx.HTTPError:
            return False
        if r.status_code >= HTTP_BAD:
            return False
        try:
            data = r.json()
        except ValueError:
            return r.status_code == HTTP_OK
        return bool(data.get("status") == "ok")
