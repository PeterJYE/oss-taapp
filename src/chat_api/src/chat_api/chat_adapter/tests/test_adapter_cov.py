"""Coverage-oriented tests for adapter request paths and helpers."""

from __future__ import annotations

import pytest

from slack_adapter import (
    ServiceAdapter,
    ServiceBackedClient,
    _get_id,
)  # type: ignore[import]
from slack_api import Channel, Message  # only for runtime construction


class DummyHTTPXClient:
    """Unified `request()` client returning small structs that look like responses."""

    def __init__(self) -> None:
        """Track close() calls for context-manager coverage."""
        self.closed = False

    def request(self, method: str, url: str, **kwargs: object) -> object:
        """Return an object with attributes accessed by the adapter.

        Health: {"ok": True}
        /channels: {"channels": [{"id": "C9", "name": "gen"}]}
        /messages: echoes json payload back into {"message": {...}}
        """

        class R:
            def __init__(
                self, method: str, url: str, kwargs: dict[str, object],
            ) -> None:
                self.method = method
                self.url = url
                self.kwargs = kwargs
                self.status_code = 200

            def json(self) -> dict[str, object]:
                if self.url == "/health":
                    return {"ok": True}
                if self.url == "/channels":
                    return {"channels": [{"id": "C9", "name": "gen"}]}
                if self.url == "/messages":
                    j = self.kwargs.get("json", {})
                    return {
                        "message": {
                            "id": "m-1",
                            "channel_id": j.get("channel_id", ""),
                            "text": j.get("text", ""),
                        },
                    }
                return {}

        return R(method, url, dict(kwargs))

    def close(self) -> None:
        """Mark the client as closed."""
        self.closed = True


def test_health_list_and_post_paths() -> None:
    """Happy paths for health, channels, and posting message."""
    http = DummyHTTPXClient()
    adapter = ServiceAdapter(lambda: http)

    if adapter.health() is not True:
        pytest.fail("health should be True")

    chs = adapter.list_channels()
    if len(chs) != 1:
        pytest.fail("expected exactly one channel")
    if not isinstance(chs[0], Channel):
        pytest.fail("expected a Channel instance")
    if chs[0].id != "C9":
        pytest.fail("channel id mismatch")

    msg = adapter.post_message("C9", "hello")
    if not isinstance(msg, Message):
        pytest.fail("expected a Message instance")
    if msg.channel_id != "C9":
        pytest.fail("message channel_id mismatch")
    if msg.id != "m-1":
        pytest.fail("message id mismatch")


def test_get_id_and_public_client_close_and_identifier() -> None:
    """Cover _get_id variants, message_identifier, and context mgmt."""
    http = DummyHTTPXClient()
    client = ServiceBackedClient(base_url="http://test", http=http)

    if _get_id({"id": "x"}) != "x":
        pytest.fail("_get_id did not return 'id'")
    if (
        _get_id(
            Message(
                message_id="m2",
                text="t",
                channel_id="c",
                ts="1.0",
            ),
        )
        != "m2"
    ):
        pytest.fail("_get_id did not extract message_id from Message")

    if client.message_identifier({"id": "ok"}) != "ok":
        pytest.fail("message_identifier happy path failed")

    try:
        client.message_identifier({"bad": "shape"})
    except ValueError:
        pass
    else:
        pytest.fail("expected ValueError for bad message shape")

    with client as c2:
        if c2 is not client:
            pytest.fail("__enter__ did not return self")
    if http.closed is not True:
        pytest.fail("HTTP client was not closed after context exit")
