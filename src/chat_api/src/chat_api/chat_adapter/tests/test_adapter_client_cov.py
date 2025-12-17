"""End-to-end adapter tests using an in-process FastAPI app and sync httpx client.

These tests exercise SlackServiceBackedClient against the real FastAPI app
without starting an external server by wrapping httpx's ASGI transport.
"""

from __future__ import annotations

# no Any in tests to satisfy ANN401
import anyio
import httpx
import pytest
from httpx import ASGITransport as _ASGITransport
from httpx import BaseTransport, Request, Response

from slack_adapter import SlackServiceBackedClient

# Import FastAPI app in-process so tests run without a real server.
try:
    from slack_service.app import app  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    app = None  # type: ignore[assignment]
    _import_error: Exception | None = exc
else:
    _import_error = None


pytestmark = pytest.mark.skipif(
    app is None,
    reason=f"slack_service not importable: {_import_error}",
)


class SyncASGITransport(BaseTransport):
    """Synchronous wrapper for httpx's async ASGI transport.

    It converts the async response into a fully materialized sync Response,
    ensuring response.stream is a SyncByteStream (what httpx.Client expects).
    """

    def __init__(self, asgi_app: object) -> None:
        """Initialize the wrapper with a FastAPI/ASGI app."""
        self._async = _ASGITransport(app=asgi_app)

    def handle_request(self, request: Request) -> Response:
        """Bridge to the async transport and return a sync Response."""

        async def _go() -> Response:
            # Get async response from ASGI transport
            async_resp: Response = await self._async.handle_async_request(request)  # type: ignore[assignment]
            # Read the entire body so we can build a sync Response
            content = await async_resp.aread()
            return Response(
                status_code=async_resp.status_code,
                headers=async_resp.headers,
                content=content,
                request=request,
                extensions=async_resp.extensions,
            )

        return anyio.run(_go)

    def close(self) -> None:
        """Close the underlying async transport."""
        anyio.run(self._async.aclose)


def _adapter_against_inmemory_service() -> SlackServiceBackedClient:
    """Create an adapter client wired to the in-process FastAPI app."""
    if app is None:  # safety; the module-level skip should already handle this
        pytest.skip(f"slack_service not importable: {_import_error}")
    transport = SyncASGITransport(app)
    http = httpx.Client(transport=transport, base_url="http://test")
    return SlackServiceBackedClient(base_url="http://test", http=http)


def test_health_true() -> None:
    """adapter.health() returns True on HTTP 200."""
    client = _adapter_against_inmemory_service()
    try:
        result = client.health()
        if result is not True:
            pytest.fail("Expected health() to be True for HTTP 200")
    finally:
        client.close()


def test_list_channels_expected_ids() -> None:
    """list_channels() includes the seeded channel IDs."""
    client = _adapter_against_inmemory_service()
    try:
        channels = client.list_channels()
        ids = {c.id for c in channels}
        if "C001" not in ids:
            pytest.fail("Expected channel id 'C001' in list_channels() result")
        if "C002" not in ids:
            pytest.fail("Expected channel id 'C002' in list_channels() result")
    finally:
        client.close()


def test_post_message_returns_ts() -> None:
    """post_message() returns a message with channel_id and a non-empty ts."""
    client = _adapter_against_inmemory_service()
    try:
        msg = client.post_message("C001", "hello")
        if msg.channel_id != "C001":
            pytest.fail("Expected returned message.channel_id to equal 'C001'")
        if not isinstance(msg.ts, str):
            pytest.fail("Expected returned message.ts to be a string")
        if len(msg.ts) == 0:
            pytest.fail("Expected returned message.ts to be non-empty")
    finally:
        client.close()

