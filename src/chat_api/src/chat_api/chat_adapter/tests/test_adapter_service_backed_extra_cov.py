"""Extra coverage tests for ServiceBackedClient and SlackServiceBackedClient."""


from __future__ import annotations

from slack_adapter import (  # type: ignore[import]
    ServiceBackedClient,
    SlackServiceBackedClient,
)
from slack_api import Message


class _RespNonMapping:
    def __init__(self) -> None:
        self.status_code = 200

    def json(self) -> object:
        # Non-mapping JSON exercises fallback branch in health()
        return ["ok", "not-a-mapping"]


class _HTTPNonMapping:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_kwargs: object) -> _RespNonMapping:
        self.calls.append((method, url))
        return _RespNonMapping()

    def close(self) -> None:
        self.calls.append(("CLOSE", "", {}))


def test_service_backed_health_with_non_mapping_json() -> None:
    """health() should fall back to status_code when JSON is not a mapping."""
    http = _HTTPNonMapping()
    client = ServiceBackedClient(base_url="http://svc", http=http)

    result = client.health()

    assert result is True
    assert http.calls, "expected at least one HTTP call"


class _HTTPClientLike:
    """Simple HTTP client-like stub used by SlackServiceBackedClient."""

    def __init__(self) -> None:
        self.closed = False

    def request(self, _method: str, url: str, **kwargs: object) -> object:
        class Resp:
            def __init__(self, url: str, kwargs: dict[str, object]) -> None:
                self.status_code = 200
                self._url = url
                self._kwargs = kwargs

            def json(self) -> dict[str, object]:
                if self._url.endswith("/health"):
                    return {"ok": True}
                if self._url.endswith("/channels"):
                    return {"channels": [{"id": "C-extra", "name": "extra"}]}
                if "/channels/" in self._url and self._url.endswith("/messages"):
                    payload = {}
                    json_payload = self._kwargs.get("json")
                    if isinstance(json_payload, dict):
                        payload = json_payload
                    return {
                        "message": {
                            "id": "m-extra",
                            "channel_id": payload.get("channel_id", ""),
                            "text": payload.get("text", ""),
                        },
                    }
                return {}

        return Resp(url, dict(kwargs))

    def close(self) -> None:
        self.closed = True


def test_slack_service_backed_uses_injected_http_client() -> None:
    """SlackServiceBackedClient should use the injected HTTP-like client."""
    http = _HTTPClientLike()
    client = SlackServiceBackedClient(base_url="http://svc")
    client._client = http

    assert client.health() is True

    channels = client.list_channels()
    assert channels
    first = channels[0]
    assert first.id == "C-extra"
    assert first.name == "extra"

    message = client.post_message("C-extra", "hi-extra")
    assert isinstance(message, Message)
    assert message.channel_id == "C-extra"
    assert "hi-extra" in message.text

    client.close()
    assert http.closed is True

