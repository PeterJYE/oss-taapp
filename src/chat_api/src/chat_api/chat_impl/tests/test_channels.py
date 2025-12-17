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


def test_list_channels_offline_two_known() -> None:
    client = SlackClient()  # offline mode
    chans = client.list_channels()
    assert len(chans) == 2
    assert [_get(c, "id") for c in chans] == ["C001", "C002"]
    assert all(_get(c, "name") for c in chans)
