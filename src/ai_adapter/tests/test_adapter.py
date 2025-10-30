"""Unit tests for the AI adapter.

These tests use small dummy objects to simulate HTTP responses and verify
adapter behavior.
"""

from __future__ import annotations

import pytest

from ai_adapter import AdapterAPIError, AIAdapter


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
    """A minimal fake http client with ``post`` and ``get`` methods."""

    def __init__(self, resp: DummyResp) -> None:
        """Create a dummy HTTP client that always returns ``resp``."""
        self._resp = resp

    def post(self, path: str, json: dict[str, object] | None = None) -> DummyResp:
        """Return the configured response for POST requests."""
        return self._resp

    def get(self, path: str) -> DummyResp:
        """Return the configured response for GET requests."""
        return self._resp


def test_generate_success() -> None:
    """generate() returns the text when the service responds 200."""
    resp = DummyResp(status_code=200, json_data={"text": "hello world"})
    adapter = AIAdapter(client=None, base_url="http://example.com")
    # monkeypatch the internal httpx client to our dummy
    adapter._http = DummyHTTP(resp)

    out = adapter.generate("hi")
    assert out == "hello world"


def test_generate_api_error() -> None:
    """generate() raises AdapterAPIError when the remote service returns >=500."""
    resp = DummyResp(status_code=500, content=b"error")
    adapter = AIAdapter(client=None, base_url="http://example.com")
    adapter._http = DummyHTTP(resp)

    with pytest.raises(AdapterAPIError):
        adapter.generate("hi")


def test_generate_with_generated_client() -> None:
    """Adapter should call into a provided generated-client instance."""

    class DummyGenClient:
        def generate(self, payload: dict[str, object]) -> dict[str, object]:
            return {"text": f"gen:{payload.get('prompt', '')}"}

    client = DummyGenClient()
    adapter = AIAdapter(client=client)

    out = adapter.generate("hello")
    assert out == "gen:hello"


def test_chat_with_generated_client() -> None:
    """Adapter.chat should concatenate message contents from the generated client."""
    class DummyGenClient:
        def chat(self, payload: dict[str, object]) -> dict[str, object]:
            msgs = payload.get("messages", [])
            return {"text": "|".join(str(m.get("content", "")) for m in msgs)}

    client = DummyGenClient()
    adapter = AIAdapter(client=client)

    out = adapter.chat([{"role": "user", "content": "hi"}, {"role": "bot", "content": "hey"}])
    assert out == "hi|hey"


def test_health_check_prefers_client() -> None:
    """health_check should prefer the generated client's health method when present."""
    class DummyGenClient:
        def health(self) -> object:
            class R:
                ok = True

            return R()

    client = DummyGenClient()
    adapter = AIAdapter(client=client)

    assert adapter.health_check() is True
