"""Tests for mail client service main endpoints."""

from collections.abc import Iterator
from http import HTTPStatus

import pytest

HTTP_OK = HTTPStatus.OK
HTTP_NOT_FOUND = HTTPStatus.NOT_FOUND
HTTP_INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.integration
def test_list_and_detail_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: C901
    """Test list and detail endpoints with mocked client."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from mail_client_service import app  # noqa: PLC0415

    error_not_found = "not found"

    class DummyMsg:
        """Dummy message for testing."""

        def __init__(self, message_id: str, subject: str | None = None) -> None:
            """Initialize dummy message."""
            self.id = message_id
            self.subject = subject
            self.from_ = "a@b.com"
            self.to = "me@me.com"
            self.date = "2025-01-01T00:00:00Z"
            self.body = "hi"

    class DummyClient:
        """Dummy client for testing."""

        def __init__(self) -> None:
            """Initialize dummy client with test messages."""
            self._msgs = [DummyMsg("m1", "s1"), DummyMsg("m2")]

        def get_messages(self, max_results: int = 10) -> Iterator[DummyMsg]:
            """Get messages iterator."""
            yield from self._msgs[:max_results]

        def get_message(self, message_id: str) -> DummyMsg:
            """Get message by ID."""
            for m in self._msgs:
                if m.id == message_id:
                    return m
            raise KeyError(error_not_found)

        def delete_message(self, message_id: str) -> bool:
            """Delete message by ID."""
            for i, m in enumerate(self._msgs):
                if m.id == message_id:
                    del self._msgs[i]
                    return True
            return False

        def mark_as_read(self, message_id: str) -> bool:
            """Mark message as read by ID."""
            return any(m.id == message_id for m in self._msgs)

    dummy = DummyClient()
    from mail_client_service.main import get_client_dep  # noqa: PLC0415

    app.dependency_overrides[get_client_dep] = lambda: dummy

    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/messages?limit=2")
    assert r.status_code == HTTP_OK
    js = r.json()
    assert isinstance(js, list)
    assert js[0]["id"] == "m1"

    r2 = client.get("/messages/m1")
    assert r2.status_code == HTTP_OK
    d = r2.json()
    assert d["id"] == "m1"

    r3 = client.post("/messages/m1/mark-as-read")
    assert r3.status_code == HTTP_OK

    r4 = client.delete("/messages/m1")
    assert r4.status_code == HTTP_OK


@pytest.mark.integration
def test_endpoints_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error handling paths for endpoints."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from mail_client_service import app  # noqa: PLC0415

    error_message = "boom"

    def bad_dep() -> None:
        """Dependency that raises an error."""
        raise RuntimeError(error_message)

    from mail_client_service.main import get_client_dep  # noqa: PLC0415

    app.dependency_overrides[get_client_dep] = bad_dep

    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/messages")
    assert r.status_code == HTTP_INTERNAL_SERVER_ERROR

    r2 = client.get("/messages/doesnotexist")
    assert r2.status_code in (HTTP_NOT_FOUND, HTTP_INTERNAL_SERVER_ERROR)
