"""Unit tests for mail client API."""

from collections.abc import Iterator

import pytest

from mail_client_api.client import Client, get_client
from mail_client_api.message import Message


class DummyMessage(Message):
    """Dummy message implementation for testing."""

    def __init__(self, msg_id: str, body: str = "Hello") -> None:
        """Initialize dummy message with ID and body."""
        self._id = msg_id
        self._from = "sender@example.com"
        self._to = "receiver@example.com"
        self._date = "2025-10-19"
        self._subject = "Test"
        self._body = body

    @property
    def id(self) -> str:
        """Return message ID."""
        return self._id

    @property
    def from_(self) -> str:
        """Return sender address."""
        return self._from

    @property
    def to(self) -> str:
        """Return recipient address."""
        return self._to

    @property
    def date(self) -> str:
        """Return message date."""
        return self._date

    @property
    def subject(self) -> str:
        """Return message subject."""
        return self._subject

    @property
    def body(self) -> str:
        """Return message body."""
        return self._body


class DummyClient(Client):
    """Concrete subclass to test abstract Client behavior."""

    def __init__(self) -> None:
        """Initialize dummy client with test storage."""
        self.storage = {"1": DummyMessage("1"), "2": DummyMessage("2")}

    def get_message(self, message_id: str) -> Message:
        """Retrieve a message by ID."""
        return self.storage.get(message_id)

    def delete_message(self, message_id: str) -> bool:
        """Delete a message by ID."""
        return self.storage.pop(message_id, None) is not None

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read by ID."""
        return message_id in self.storage

    def get_messages(self, max_results: int = 10) -> Iterator[Message]:
        """Get an iterator of messages."""
        return iter(list(self.storage.values())[:max_results])


def test_client_is_abstract() -> None:
    """Ensure Client cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Client()


def test_get_client_not_implemented() -> None:
    """Ensure get_client() raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        get_client()


def test_dummy_client_get_message() -> None:
    """Test DummyClient can retrieve a message by ID."""
    client = DummyClient()
    msg = client.get_message("1")
    assert isinstance(msg, Message)
    assert msg.id == "1"


def test_dummy_client_delete_message() -> None:
    """Test DummyClient can delete messages and verify deletion."""
    client = DummyClient()
    assert client.delete_message("1") is True
    assert client.get_message("1") is None


def test_dummy_client_mark_as_read() -> None:
    """Test DummyClient can mark messages as read."""
    client = DummyClient()
    assert client.mark_as_read("2") is True
    assert client.mark_as_read("nonexistent") is False


def test_dummy_client_get_messages_iterator() -> None:
    """Test DummyClient returns an iterator of messages."""
    client = DummyClient()
    messages = client.get_messages()
    assert isinstance(messages, Iterator)
    msgs = list(messages)
    assert all(isinstance(m, Message) for m in msgs)
