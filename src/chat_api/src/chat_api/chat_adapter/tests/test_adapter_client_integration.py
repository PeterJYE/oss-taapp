"""Integration-style tests for the Slack adapter using dummy HTTPX clients."""

from __future__ import annotations

from typing import ClassVar

import pytest

from slack_adapter import SlackServiceBackedClient


class DummyResponse:
    """Minimal stand-in for httpx.Response."""

    status_code: ClassVar[int] = 200
    content: ClassVar[bytes] = b"{}"
    headers: ClassVar[dict[str, str]] = {}

    def json(self) -> dict[str, object]:
        """Return a basic JSON body."""
        return {}


class DummyHTTPXClient:
    """Fake httpx.Client that records calls and returns DummyResponse."""

    def __init__(self) -> None:
        """Initialize the recorder store."""
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> DummyResponse:
        """Record a call and return a default response."""
        self.calls.append((method, url, dict(kwargs)))
        return DummyResponse()


class DummyGeneratedClient:
    """Lightweight simulation of the generated client with a single getter."""

    def __init__(self) -> None:
        """Initialize with a dummy HTTPX client."""
        self._httpx = DummyHTTPXClient()

    def get_httpx_client(self) -> DummyHTTPXClient:
        """Expose the HTTPX-like client the adapter will use."""
        return self._httpx


def test_health_endpoint() -> None:
    """Ensure adapter.health() delegates correctly to the generated client."""
    adapter = SlackServiceBackedClient()
    # Test-only injection of the generated client object.
    adapter._client = DummyGeneratedClient()  # noqa: SLF001

    result = adapter.health()
    if result is not True:
        pytest.fail("Health endpoint should return True for HTTP 200")


def test_list_channels() -> None:
    """Verify list_channels() maps the JSON into Channel models."""
    dummy_channels = [{"id": "C123", "name": "general"}]

    class DummyResponseChannels(DummyResponse):
        def json(self) -> dict[str, object]:
            return {"channels": dummy_channels}

    class SmartHTTPXClient(DummyHTTPXClient):
        def request(
            self, _method: str, url: str, **_kwargs: object,
        ) -> DummyResponse:  # type: ignore[override]
            if url.endswith("/channels"):
                return DummyResponseChannels()
            pytest.fail(
                f"Unexpected URL in SmartHTTPXClient.request: {url}",
            )

    class SmartClient(DummyGeneratedClient):
        def get_httpx_client(
            self,
        ) -> SmartHTTPXClient:  # type: ignore[override]
            return SmartHTTPXClient()

    adapter = SlackServiceBackedClient()
    adapter._client = SmartClient()  # noqa: SLF001

    channels = adapter.list_channels()
    if not isinstance(channels, list):
        pytest.fail("channels should be a list")
    if not channels:
        pytest.fail("channels should not be empty")
    if channels[0].name != "general":
        pytest.fail("expected first channel name to be 'general'")


def test_post_message() -> None:
    """Verify post_message() maps the JSON into Message model."""
    dummy_message = {"id": "m-1", "channel_id": "C123", "text": "Hello"}

    class DummyResponseMessage(DummyResponse):
        def json(self) -> dict[str, object]:
            return {"message": dummy_message}

    class SmartHTTPXClient(DummyHTTPXClient):
        def request(
            self, _method: str, url: str, **_kwargs: object,
        ) -> DummyResponse:  # type: ignore[override]
            if url.endswith("/messages"):
                return DummyResponseMessage()
            pytest.fail(
                f"Unexpected URL in SmartHTTPXClient.request: {url}",
            )

    class SmartClient(DummyGeneratedClient):
        def get_httpx_client(
            self,
        ) -> SmartHTTPXClient:  # type: ignore[override]
            return SmartHTTPXClient()

    adapter = SlackServiceBackedClient()
    adapter._client = SmartClient()  # noqa: SLF001

    message = adapter.post_message("C123", "Hello")
    if message.text != "Hello":
        pytest.fail("message text mismatch")
    if message.channel_id != "C123":
        pytest.fail("message channel_id mismatch")
