"""Unit tests for the OpenAI service adapter.

These tests use small dummy objects to simulate HTTP responses and verify
adapter behavior without requiring the FastAPI service or OpenAI credentials.
"""

from __future__ import annotations

import pytest

from ai_adapter import AdapterAPIError, OpenAIServiceAdapter


class DummyResp:
    """A minimal fake response object used by DummyHTTP."""

    def __init__(self, status_code: int = 200, json_data: dict[str, object] | None = None, content: bytes | str = b"") -> None:
        """Initialize the fake response with status, json payload and content."""
        self.status_code = status_code
        self._json = json_data or {}
        self.content = content

    def json(self) -> dict[str, object]:
        """Return the stored JSON payload."""
        return self._json


class DummyHTTP:
    """A minimal fake http client with ``post``, ``get``, and ``delete`` methods."""

    def __init__(self, resp: DummyResp) -> None:
        """Create a dummy HTTP client that always returns ``resp``."""
        self._resp = resp

    def post(self, path: str, json: dict[str, object] | None = None) -> DummyResp:
        """Return the configured response for POST requests."""
        return self._resp

    def get(self, path: str) -> DummyResp:
        """Return the configured response for GET requests."""
        return self._resp
    def delete(self, path: str) -> DummyResp:
        """Return the configured response for DELETE requests."""
        return self._resp


def test_create_conversation_success() -> None:
    """create_conversation returns conversation_id on 200."""
    resp = DummyResp(status_code=200, json_data={"conversation_id": "abc"})
    adapter = OpenAIServiceAdapter(base_url="http://example.com", subject="user1")
    adapter._http = DummyHTTP(resp)  # type: ignore[attr-defined]
    assert adapter.create_conversation() == "abc"


def test_generate_response_api_error_unauthorized() -> None:
    """generate_response raises AdapterAPIError on 401 without API key."""
    resp = DummyResp(status_code=401, content=b"Missing API key")
    adapter = OpenAIServiceAdapter(base_url="http://example.com", subject="user1")
    adapter._http = DummyHTTP(resp)  # type: ignore[attr-defined]
    with pytest.raises(AdapterAPIError):
        adapter.generate_response(["hello"])  # no API key -> expect 401


def test_get_conversation_success() -> None:
    """get_conversation returns dict when 200."""
    conv = {"id": "abc", "messages": [["user", "hi"]]}
    resp = DummyResp(status_code=200, json_data=conv)
    adapter = OpenAIServiceAdapter(base_url="http://example.com", subject="user1")
    adapter._http = DummyHTTP(resp)  # type: ignore[attr-defined]
    data = adapter.get_conversation("abc")
    assert data["id"] == "abc"


def test_delete_conversation_success() -> None:
    """delete_conversation returns True on ok."""
    resp = DummyResp(status_code=200, json_data={"ok": True})
    adapter = OpenAIServiceAdapter(base_url="http://example.com", subject="user1")
    adapter._http = DummyHTTP(resp)  # type: ignore[attr-defined]
    assert adapter.delete_conversation("abc") is True


def test_health_check_true_on_ok_status() -> None:
    """health_check returns True when status is ok."""
    resp = DummyResp(status_code=200, json_data={"status": "ok"})
    adapter = OpenAIServiceAdapter(base_url="http://example.com", subject="user1")
    adapter._http = DummyHTTP(resp)  # type: ignore[attr-defined]
    assert adapter.health_check() is True
