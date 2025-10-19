import pytest
from collections.abc import Iterator
from mail_client_api.client import Client, get_client
from mail_client_api.message import Message
#PYTHONPATH=src/mail_client_api/src pytest -v src/mail_client_api/tests/test_client_unit.py


class DummyMessage(Message):
    def __init__(self, msg_id, body="Hello"):
        self._id = msg_id
        self._from = "sender@example.com"
        self._to = "receiver@example.com"
        self._date = "2025-10-19"
        self._subject = "Test"
        self._body = body

    @property
    def id(self): return self._id

    @property
    def from_(self): return self._from

    @property
    def to(self): return self._to

    @property
    def date(self): return self._date

    @property
    def subject(self): return self._subject

    @property
    def body(self): return self._body


class DummyClient(Client):
    """Concrete subclass to test abstract Client behavior."""

    def __init__(self):
        self.storage = {"1": DummyMessage("1"), "2": DummyMessage("2")}

    def get_message(self, message_id: str) -> Message:
        return self.storage.get(message_id)

    def delete_message(self, message_id: str) -> bool:
        return self.storage.pop(message_id, None) is not None

    def mark_as_read(self, message_id: str) -> bool:
        return message_id in self.storage

    def get_messages(self, max_results: int = 10) -> Iterator[Message]:
        return iter(list(self.storage.values())[:max_results])


# --------------------- TESTS ----------------------

def test_client_is_abstract():
    """Ensure Client cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Client()


def test_get_client_not_implemented():
    """Ensure get_client() raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        get_client()


def test_dummy_client_get_message():
    client = DummyClient()
    msg = client.get_message("1")
    assert isinstance(msg, Message)
    assert msg.id == "1"


def test_dummy_client_delete_message():
    client = DummyClient()
    assert client.delete_message("1") is True
    assert client.get_message("1") is None


def test_dummy_client_mark_as_read():
    client = DummyClient()
    assert client.mark_as_read("2") is True
    assert client.mark_as_read("nonexistent") is False


def test_dummy_client_get_messages_iterator():
    client = DummyClient()
    messages = client.get_messages()
    assert isinstance(messages, Iterator)
    msgs = list(messages)
    assert all(isinstance(m, Message) for m in msgs)