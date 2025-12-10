from __future__ import annotations

from typing import Any, Dict
from slack_impl.slack_client import SlackClient, Message


class DummyResp:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError("unexpected error path in test")

    def json(self):
        return self._payload


class DummyHTTP:
    def __init__(self):
        self.called = []

    def get(self, url: str, params: Dict[str, Any] | None = None):
        self.called.append(("GET", url, params))
        if url == "/health":
            return DummyResp({"ok": True})
        if url == "/conversations.list":
            return DummyResp(
                {
                    "channels": [
                        {"id": "C77", "name": "dev"},
                        {"id": "C88", "name": "ops"},
                    ]
                }
            )
        if url == "/conversations.history":
            return DummyResp(
                {"messages": [{"text": "hi", "ts": "1.0"}, {"text": "yo", "ts": "2.0"}]}
            )
        return DummyResp({})

    def post(self, url: str, json: Dict[str, Any] | None = None):
        self.called.append(("POST", url, json))
        if url == "/chat.postMessage":
            return DummyResp(
                {
                    "message": {
                        "channel": json.get("channel"),
                        "text": json.get("text"),
                        "ts": "3.0",
                    }
                }
            )
        return DummyResp({})


def test_online_mode_paths() -> None:
    http = DummyHTTP()
    c = SlackClient(base_url="http://service", token="tkn", http=http)  # online mode
    assert c.offline is False

    # health online branch
    assert c.health() is True

    # list_channels online mapping
    chans = c.list_channels()
    names = [ch.name for ch in chans]
    assert names == ["dev", "ops"]

    # post_message online mapping
    msg = c.post_message("C77", "hey there")
    assert (
        isinstance(msg, Message) and msg.channel_id == "C77" and "hey there" in msg.text
    )

    # get_channel_history online mapping + limit param exercised
    hist = c.get_channel_history("C77", limit=2)
    assert len(hist) == 2 and hist[0].text == "hi"
