"""OpenAI Client Service adapter.

Explicit HTTP client for service endpoints, no dynamic attribute access.

Endpoints:
- POST /ai/generate_response (no auth required)
- POST /ai/compose-response (requires OAuth)
- POST /ai/conversations (requires OAuth)
- GET  /ai/conversations/{conversation_id} (requires OAuth)
- DELETE /ai/conversations/{conversation_id} (requires OAuth)
- GET  /health
"""
# mypy: disable-error-code=no-any-return

from __future__ import annotations

from importlib import import_module
from typing import Any
from urllib.parse import urlparse

import httpx

# Try to import AIInterface, but make it optional
try:
    from ai_api import AIInterface  # type: ignore[attr-defined]
except ImportError:
    # If ai_api is not available, define a stub for type checking
    from abc import ABC, abstractmethod

    class AIInterface(ABC):  # type: ignore[no-redef]
        """Stub AIInterface if ai_api is not available."""

        @abstractmethod
        def generate_response(
            self,
            user_input: str,
            system_prompt: str,
            response_schema: dict[str, Any] | None = None,
        ) -> str | dict[str, Any]:
            """Generate a response from the AI."""
            raise NotImplementedError

HTTP_OK = 200
HTTP_BAD = 400


def _load_test_client() -> tuple[Any | None, Any | None]:
    """Attempt to import FastAPI's TestClient and the service app lazily."""
    test_client_cls: Any | None = None
    service_app: Any | None = None

    try:
        testclient_mod = import_module("fastapi.testclient")
    except ImportError:
        testclient_mod = None
    if testclient_mod is not None:
        test_client_cls = getattr(testclient_mod, "TestClient", None)

    candidate_modules = [
        "openai_client_service.main",
        "openai_client_service.src.openai_client_service.main",
    ]
    for module_name in candidate_modules:
        try:
            service_mod = import_module(module_name)
        except ImportError:
            continue
        app_candidate = getattr(service_mod, "app", None)
        if app_candidate is not None and callable(app_candidate):
            service_app = app_candidate
            break

    return test_client_cls, service_app


class AdapterError(Exception):
    """Base adapter exception."""


class AdapterNetworkError(AdapterError):
    """Network-level error communicating with the remote service."""


class AdapterAPIError(AdapterError):
    def __init__(self, status_code: int, content: bytes | str | None = None) -> None:
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

    def __init__(self, *, base_url: str, session_id: str | None = None, timeout: float = 5.0) -> None:
        """Initialize the adapter with base URL and optional session cookie.

        Args:
            base_url: The base URL of the OpenAI Client Service
            session_id: Optional session ID cookie value from OAuth authentication.
                       Required for OAuth-protected endpoints, not needed for /ai/generate_response
            timeout: Request timeout in seconds

        """
        if not base_url:
            msg = "base_url is required"
            raise ValueError(msg)

        self._base_url = base_url
        self._timeout = timeout
        self._cookies: dict[str, str] = {}
        if session_id:
            self._cookies["session_id"] = session_id

        self._http: Any
        host = (urlparse(base_url).hostname or "").lower()
        test_client_cls, service_app = _load_test_client()
        if host == "testserver" and test_client_cls is not None and service_app is not None:
            test_client = test_client_cls(service_app, base_url=base_url)
            test_client.cookies.update(self._cookies)
            self._http = test_client
            return

        transport: httpx.BaseTransport | None = None
        if host == "testserver" and service_app is not None:
            transport = httpx.ASGITransport(app=service_app)  # type: ignore[arg-type,assignment]

        self._http = httpx.Client(base_url=base_url, cookies=self._cookies, timeout=timeout, transport=transport)

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        """POST /ai/generate_response returning string or structured dict.

        This endpoint does not require OAuth authentication. It uses the API key
        from the service's .env file.

        Args:
            user_input: The text provided by the user
            system_prompt: The instruction set for the AI
            response_schema: Optional JSON schema for structured output

        Returns:
            String response if no schema provided, or dict if schema provided

        Raises:
            AdapterAPIError: On non-2xx responses
            AdapterNetworkError: On network errors

        """
        payload: dict[str, Any] = {
            "user_input": user_input,
            "system_prompt": system_prompt,
        }
        if response_schema is not None:
            payload["response_schema"] = response_schema

        try:
            r = self._http.post("/ai/generate_response", json=payload)
        except httpx.HTTPError as exc:
            raise AdapterNetworkError(exc) from exc
        if r.status_code >= HTTP_BAD:
            raise AdapterAPIError(r.status_code, r.content)
        return r.json()

    def compose_response(self, messages: list[str], *, conversation_id: str | None = None) -> dict[str, object | None]:
        """POST /ai/compose-response returning content, tokens_used, conversation_id.

        This endpoint requires OAuth authentication (session_id cookie).

        Raises AdapterAPIError on non-2xx responses.
        """
        payload: dict[str, object | None] = {"messages": messages, "conversation_id": conversation_id}
        try:
            r = self._http.post("/ai/compose-response", json=payload)
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
            status_str: str = status_val
            if status_str == "ok":
                return True
        return False


class AIAdapter(AIInterface):
    """Adapter that implements AIInterface using OpenAIServiceAdapter.

    This adapter wraps the OpenAIServiceAdapter and exposes only
    the methods defined in the shared AIInterface.
    """

    def __init__(
        self,
        service_adapter: OpenAIServiceAdapter | None = None,
        *,
        base_url: str = "",
        session_id: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the adapter with an OpenAIServiceAdapter instance.

        Args:
            service_adapter: The OpenAIServiceAdapter to wrap. If None, creates a new instance.
            base_url: The base URL of the OpenAI Client Service (required if service_adapter is None)
            session_id: Optional session ID cookie value (not needed for generate_response)
            timeout: Request timeout in seconds

        """
        if service_adapter is not None:
            self._adapter = service_adapter
        else:
            if not base_url:
                msg = "base_url is required when service_adapter is None"
                raise ValueError(msg)
            self._adapter = OpenAIServiceAdapter(base_url=base_url, session_id=session_id, timeout=timeout)

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        """Generate a response from the AI.

        Args:
            user_input: The text provided by the chat user.
            system_prompt: The instruction set (e.g., "You are a helpful assistant...").
            response_schema: An optional JSON schema (dict).
                            If provided, the AI must return a structured Dict matching
                            this schema. If None, the AI returns a conversational String.

        Returns:
            A string (conversation) or a Dict (structured action data).

        """
        return self._adapter.generate_response(
            user_input=user_input,
            system_prompt=system_prompt,
            response_schema=response_schema,
        )
