"""Tests for service adapter integration."""

import sys
import types

import pytest

from adapter.service_client_adapter import ServiceClientAdapter

EXPECTED_MESSAGE_COUNT = 2


@pytest.mark.unit
def test_service_message_and_adapter_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test ServiceMessage and adapter roundtrip with fake generated models."""

    class FakeSummary:
        """Fake message summary for testing."""

        def __init__(self, message_id: str, subject: str) -> None:
            """Initialize fake summary with message ID and subject."""
            self.id = message_id
            self.subject = subject

    class FakeDetail:
        """Fake message detail for testing."""

        def __init__(  # noqa: PLR0913
            self,
            message_id: str,
            from_: str,
            to: str,
            date: str,
            subject: str,
            body: str,
        ) -> None:
            """Initialize fake detail with message fields."""
            self.id = message_id
            self.from_ = from_
            self.to = to
            self.date = date
            self.subject = subject
            self.body = body

    fake_api = types.SimpleNamespace()

    def list_messages_sync(max_results: int = 10) -> types.SimpleNamespace:
        """Return fake message list."""
        return types.SimpleNamespace(
            messages=[FakeSummary("m1", "s1"), FakeSummary("m2", "s2")],
        )

    def get_message_sync(message_id: str) -> FakeDetail:
        """Return fake message detail."""
        return FakeDetail(message_id, "a@b.com", "me@me.com", "2025-01-01T00:00:00Z", "sub", "body")

    fake_api.messages = types.SimpleNamespace(
        list_messages=types.SimpleNamespace(sync=list_messages_sync),
        get_message=types.SimpleNamespace(sync=get_message_sync),
        delete_message=types.SimpleNamespace(sync=lambda **_kw: None),
        mark_as_read=types.SimpleNamespace(sync=lambda **_kw: None),
    )

    class FakeClient:
        """Fake generated client for testing."""

        def __init__(self, _base_url: str = "http://x") -> None:
            """Initialize fake client with messages API."""
            self.messages = fake_api.messages

    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=FakeClient))

    adapter = ServiceClientAdapter(base_url="http://x")

    msgs = list(adapter.get_messages(max_results=10))
    assert len(msgs) == EXPECTED_MESSAGE_COUNT
    assert msgs[0].id == "m1"

    detail = adapter.get_message("m1")
    assert detail.id == "m1"
    assert detail.from_ == "a@b.com"

    assert adapter.mark_as_read("m1") is True
    assert adapter.delete_message("m1") is True
