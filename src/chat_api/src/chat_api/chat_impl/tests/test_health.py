from slack_impl import SlackClient


def test_health_true() -> None:
    client = SlackClient()
    assert client.health() is True
