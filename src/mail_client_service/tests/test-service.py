import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from mail_client_service.main import app, get_client
pytest
@pytest.fixture(autouse=True)
def mock_client(monkeypatch):
    mock = AsyncMock()
    mock.list_messages.return_value = [{"id": "123", "subject": "Hello"}]
    mock.get_message.return_value = {"id": "123", "subject": "Hello", "body": "World"}
    mock.mark_as_read.return_value = {"id": "123", "read": True}
    mock.delete_message.return_value = {"id": "123", "deleted": True}

    monkeypatch.setattr("mail_client_service.main.get_client", lambda: mock)
    return mock

client = TestClient(app)

def test_get_messages(mock_client):
    resp = client.get("/messages")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "123", "subject": "Hello"}]

def test_get_single_message(mock_client):
    resp = client.get("/messages/123")
    assert resp.status_code == 200
    assert resp.json()["id"] == "123"

def test_mark_as_read(mock_client):
    resp = client.post("/messages/123/mark-as-read")
    assert resp.status_code == 200
    assert resp.json()["read"] is True

def test_delete_message(mock_client):
    resp = client.delete("/messages/123")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
