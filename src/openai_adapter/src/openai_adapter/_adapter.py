"""OpenAI Client Service adapter.

Explicit HTTP client for five endpoints, no dynamic attribute access.

Endpoints:
- POST /ai/generate-response
- POST /ai/conversations
- GET  /ai/conversations/{conversation_id}
- DELETE /ai/conversations/{conversation_id}
- GET  /health
"""
# mypy: disable-error-code=no-any-return

from __future__ import annotations

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

    Requires a valid session cookie for authentication.
    Use OAuth login flow to obtain a session_id cookie before calling this adapter.
    """

    def __init__(self, *, base_url: str, session_id: str, timeout: float = 5.0) -> None:
        """Initialize the adapter with base URL and session cookie.

        Args:
            base_url: The base URL of the OpenAI Client Service
            session_id: The session ID cookie value from OAuth authentication
            timeout: Request timeout in seconds

        """
        if not base_url:
            msg = "base_url is required"
            raise ValueError(msg)
        if not session_id:
            msg = "session_id is required"
            raise ValueError(msg)

        self._base_url = base_url
        self._timeout = timeout
        self._cookies: dict[str, str] = {"session_id": session_id}

        transport: httpx.BaseTransport | None = None
        host = (urlparse(base_url).hostname or "").lower()
        if host == "testserver":
            try:
                from openai_client_service.main import app  # noqa: PLC0415 - lazy import for tests

                transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type,assignment]
            except ImportError:
                transport = None

        self._http = httpx.Client(base_url=base_url, cookies=self._cookies, timeout=timeout, transport=transport)

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
        data = r.json()
        return dict(data)

    def delete_conversation(self, conversation_id: str) -> bool:
        """DELETE /ai/conversations/{id} -> returns ok boolean in body."""
        try:
            r = self._http.delete(f"/ai/conversations/{conversation_id}")
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        body: dict[str, object] = r.json() if r.content else {"ok": True}
        ok: object = body.get("ok", True)
        if isinstance(ok, bool):
            return ok
        return True

    def health_check(self) -> bool:
        """GET /health -> bool."""
        try:
            r = self._http.get("/health")
        except httpx.HTTPError:
            return False
        if r.status_code >= HTTP_BAD:
            return False
        try:
            data: dict[str, object] = r.json()  # type: ignore[assignment]
        except ValueError:
            return r.status_code == HTTP_OK
        status_val: object = data.get("status")
        if isinstance(status_val, str):
            # Narrowed to str by isinstance check
            status_str: str = status_val
            if status_str == "ok":
                return True
        return False
