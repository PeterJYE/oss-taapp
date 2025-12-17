"""Additional tests to improve coverage for service_client_adapter.py."""

import sys
import types
from unittest.mock import Mock

import pytest
from adapter.service_client_adapter import ServiceClientAdapter


class FakeSummary:
    """Fake message summary for testing."""

    def __init__(self, message_id: str, subject: str) -> None:
        """Initialize fake summary."""
        self.id = message_id
        self.subject = subject


class FakeDetail:
    """Fake message detail for testing."""

    def __init__(self, message_id: str) -> None:
        """Initialize fake detail."""
        self.id = message_id
        self.from_ = "from@example.com"
        self.to = "to@example.com"
        self.date = "2025-01-01T00:00:00Z"
        self.subject = "Subject"
        self.body = "Body"


def test_get_messages_typeerror_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_messages TypeError path (line 204-205)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        list_messages=types.SimpleNamespace(sync=lambda message_id: types.SimpleNamespace(messages=[])),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    messages = list(adapter.get_messages())
    assert messages == []


def test_get_message_typeerror_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_message TypeError path (line 229-230)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        get_message=types.SimpleNamespace(sync=lambda message_id: FakeDetail("m1")),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    result = adapter.get_message("m1")
    assert result is not None


def test_delete_message_typeerror_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete_message TypeError path (line 256-257)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        delete_message=types.SimpleNamespace(sync=lambda message_id: types.SimpleNamespace(ok=True)),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    result = adapter.delete_message("m1")
    assert result is True


def test_mark_as_read_typeerror_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mark_as_read TypeError path (line 256-257)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        mark_as_read=types.SimpleNamespace(sync=lambda message_id: types.SimpleNamespace(ok=True)),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    result = adapter.mark_as_read("m1")
    assert result is True


def test_delete_message_none_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete_message when sync returns None (line 231)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        delete_message=types.SimpleNamespace(sync=lambda message_id: None),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    result = adapter.delete_message("m1")
    assert result is True


def test_mark_as_read_none_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mark_as_read when sync returns None (line 258)."""
    fake_api = types.SimpleNamespace()
    fake_api.messages = types.SimpleNamespace(
        mark_as_read=types.SimpleNamespace(sync=lambda message_id: None),
    )
    fake_client = types.SimpleNamespace(messages=fake_api.messages)
    monkeypatch.setitem(sys.modules, "generated_client", types.SimpleNamespace(Client=lambda base_url: fake_client))
    adapter = ServiceClientAdapter(base_url="http://x")
    result = adapter.mark_as_read("m1")
    assert result is True

