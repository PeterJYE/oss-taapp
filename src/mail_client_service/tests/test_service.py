"""Tests for mail client service endpoints.

Note: These tests are deprecated. Use test_main_endpoints.py instead.
This file may have import issues due to the package structure.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

HTTP_OK = HTTPStatus.OK


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.fixture(autouse=True)
def mock_client(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Fixture to mock the mail client for all tests."""
    pytest.importorskip("fastapi")
    from mail_client_service.main import app, get_client_dep  # noqa: PLC0415

    mock = AsyncMock()

    class MockMessage:
        """Mock message for testing."""

        def __init__(self) -> None:
            """Initialize mock message."""
            self.id = "123"
            self.subject = "Hello"
            self.from_ = "a@b.com"
            self.to = "me@me.com"
            self.date = "2025-01-01"
            self.body = "World"

    mock.get_messages.return_value = iter([MockMessage()])
    mock.get_message.return_value = MockMessage()
    mock.mark_as_read.return_value = True
    mock.delete_message.return_value = True

    app.dependency_overrides[get_client_dep] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.fixture
def client() -> object:
    """Create a test client."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from mail_client_service.main import app  # noqa: PLC0415

    return TestClient(app)


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.mark.usefixtures("mock_client")
def test_get_messages(client: object) -> None:
    """Test GET /messages endpoint."""
    resp = client.get("/messages")
    assert resp.status_code == HTTP_OK
    json_data = resp.json()
    assert isinstance(json_data, list)
    assert len(json_data) > 0
    assert json_data[0]["id"] == "123"


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.mark.usefixtures("mock_client")
def test_get_single_message(client: object) -> None:
    """Test GET /messages/{id} endpoint."""
    resp = client.get("/messages/123")
    assert resp.status_code == HTTP_OK
    assert resp.json()["id"] == "123"


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.mark.usefixtures("mock_client")
def test_mark_as_read(client: object) -> None:
    """Test POST /messages/{id}/mark-as-read endpoint."""
    resp = client.post("/messages/123/mark-as-read")
    assert resp.status_code == HTTP_OK
    json_data = resp.json()
    assert "ok" in json_data or json_data.get("ok") is True


@pytest.mark.skip(reason="This test file has import issues. Use test_main_endpoints.py instead.")
@pytest.mark.usefixtures("mock_client")
def test_delete_message(client: object) -> None:
    """Test DELETE /messages/{id} endpoint."""
    resp = client.delete("/messages/123")
    assert resp.status_code == HTTP_OK
    json_data = resp.json()
    assert "ok" in json_data or json_data.get("ok") is True
