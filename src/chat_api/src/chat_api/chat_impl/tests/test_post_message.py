from typing import Any

from slack_impl import SlackClient


def _get(obj: Any, key: str) -> Any:
    if hasattr(obj, key):
        return getattr(obj, key)
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict) and key in data:
            return data[key]
    raise AssertionError(f"cannot read {key!r} from {obj!r}")


def test_post_message_offline_sanitizes_and_returns_ts() -> None:
    client = SlackClient()  # offline mode
    msg = client.post_message("C001", "  hello   world  ")
    assert _get(msg, "channel_id") == "C001"
    assert _get(msg, "text") == "hello world"
    ts = _get(msg, "ts")
    assert isinstance(ts, str) and len(ts) > 0
