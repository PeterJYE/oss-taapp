from slack_impl.slack_client import (
    SlackClient,
    sanitize_text,
    get_slack_client,
    Channel,
    Message,
)


def test_offline_basics_health_channels_history_and_post() -> None:
    c = SlackClient()  # offline mode
    assert c.offline is True
    assert c.health() is True

    chans = c.list_channels()
    assert [ch.to_dict() for ch in chans] == [
        {"id": "C001", "name": "general"},
        {"id": "C002", "name": "random"},
    ]

    msg = c.post_message("C001", "  hi\tthere\nfriend ")
    assert isinstance(msg, Message)
    assert msg.channel_id == "C001"
    assert "hi there friend" in msg.text  # whitespace collapsed

    hist = c.get_channel_history("C001", limit=1)
    assert len(hist) == 1 and isinstance(hist[0], Message)

    c.close()  # offline: no http client -> just returns


def test_sanitize_text_and_factory() -> None:
    s = sanitize_text("\x00Hi\r\n\x01there  \n\nfriend\t\t", max_len=20)
    assert "Hi there friend" in s
    # factory should return offline client when args missing
    c = get_slack_client()
    assert isinstance(c, SlackClient) and c.offline is True


def test_value_objects_roundtrip() -> None:
    ch = Channel("C123", "dev")
    assert ch.to_dict() == {"id": "C123", "name": "dev"}
    m = Message(channel_id="C123", text="t", ts="1.0", id="m1")
    assert m.to_dict()["channel_id"] == "C123"
