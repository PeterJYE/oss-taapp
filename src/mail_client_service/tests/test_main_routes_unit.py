"""FastAPI route tests for `mail_client_service.main`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from starlette import status

from mail_client_service.src import main
from mail_client_service.src.main import MessageDetail

EXPECTED_MESSAGE_COUNT = 2
STATUS_INTERNAL_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
STATUS_NOT_FOUND = status.HTTP_404_NOT_FOUND
STATUS_BAD_REQUEST = status.HTTP_400_BAD_REQUEST

if TYPE_CHECKING:
    from collections.abc import Iterable


class DummyMessage:
    """Simple message DTO used for unit tests."""

    def __init__(self, message_id: str, subject: str | None) -> None:
        """Store minimal message attributes."""
        self.id = message_id
        self.subject = subject
        self.from_ = "from@example.com"
        self.to = "to@example.com"
        self.date = "2025-01-01T00:00:00Z"
        self.body = "body"


class DummyClient:
    """Fake generated client used to drive route handlers."""

    def __init__(self, *, should_fail: bool = False) -> None:
        """Initialise the fake client with optional failure flag."""
        self._fail = should_fail
        self._messages = [DummyMessage("m1", "s1"), DummyMessage("m2", None)]

    def get_messages(self, max_results: int = 10) -> Iterable[DummyMessage]:
        """Return the requested number of fake messages."""
        if self._fail:
            error_message = "boom"
            raise RuntimeError(error_message)
        return iter(self._messages[:max_results])

    def get_message(self, message_id: str) -> DummyMessage:
        """Return a single fake message, optionally raising to simulate errors."""
        if self._fail:
            error_message = "not found"
            raise KeyError(error_message)
        return DummyMessage(message_id, "subject")

    def mark_as_read(self, message_id: str) -> bool:
        """Pretend to mark a message as read."""
        _ = message_id
        return not self._fail

    def delete_message(self, message_id: str) -> bool:
        """Pretend to delete a message."""
        _ = message_id
        return not self._fail


def test_list_messages_success() -> None:
    """Successful list_messages returns two entries."""
    data = main.list_messages(client=DummyClient())
    assert len(data) == EXPECTED_MESSAGE_COUNT
    assert data[0].id == "m1"


def test_list_messages_failure() -> None:
    """Failing backend surfaces as HTTP 500."""
    with pytest.raises(HTTPException) as exc:
        main.list_messages(client=DummyClient(should_fail=True))
    assert exc.value.status_code == STATUS_INTERNAL_ERROR


def test_get_message_success() -> None:
    """Message details endpoint returns MessageDetail payload."""
    detail = main.get_message_detail(message_id="m1", client=DummyClient())
    assert isinstance(detail, MessageDetail)
    assert detail.subject == "subject"


def test_get_message_not_found() -> None:
    """Missing messages return HTTP 404."""
    with pytest.raises(HTTPException) as exc:
        main.get_message_detail(message_id="m1", client=DummyClient(should_fail=True))
    assert exc.value.status_code == STATUS_NOT_FOUND


def test_mark_as_read_failure() -> None:
    """Mark-as-read failure yields HTTP 400."""
    with pytest.raises(HTTPException) as exc:
        main.mark_message_as_read(message_id="m1", client=DummyClient(should_fail=True))
    assert exc.value.status_code == STATUS_BAD_REQUEST


def test_delete_message_failure() -> None:
    """Delete failure surfaces as HTTP 400."""
    with pytest.raises(HTTPException) as exc:
        main.delete_message(message_id="m1", client=DummyClient(should_fail=True))
    assert exc.value.status_code == STATUS_BAD_REQUEST

