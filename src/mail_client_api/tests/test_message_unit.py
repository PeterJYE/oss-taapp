import pytest
from mail_client_api.message import Message, get_message
#PYTHONPATH=src/mail_client_api/src pytest -v src/mail_client_api/tests/test_message_unit.py

class DummyMessage(Message):
    """Concrete subclass to test abstract behavior."""

    def __init__(self, msg_id, from_, to, date, subject, body):
        self._id = msg_id
        self._from = from_
        self._to = to
        self._date = date
        self._subject = subject
        self._body = body

    @property
    def id(self):
        return self._id

    @property
    def from_(self):
        return self._from

    @property
    def to(self):
        return self._to

    @property
    def date(self):
        return self._date

    @property
    def subject(self):
        return self._subject

    @property
    def body(self):
        return self._body


# -------------------- TESTS -------------------------------

def test_message_is_abstract():
    """Ensure Message cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Message()  # abstract class


def test_get_message_not_implemented():
    """Ensure get_message() raises NotImplementedError until overridden."""
    with pytest.raises(NotImplementedError):
        get_message("id123", "rawdata")


def test_dummy_message_properties():
    """Ensure DummyMessage correctly exposes all properties."""
    msg = DummyMessage(
        msg_id="123",
        from_="alice@example.com",
        to="bob@example.com",
        date="2025-10-19",
        subject="Hello!",
        body="This is a test."
    )

    assert msg.id == "123"
    assert msg.from_ == "alice@example.com"
    assert msg.to == "bob@example.com"
    assert msg.date == "2025-10-19"
    assert msg.subject == "Hello!"
    assert msg.body == "This is a test."


def test_dummy_message_str_properties_are_strings():
    """Ensure all properties return strings."""
    msg = DummyMessage("1", "a@a.com", "b@b.com", "today", "hi", "msg")
    for attr in [msg.id, msg.from_, msg.to, msg.date, msg.subject, msg.body]:
        assert isinstance(attr, str)
