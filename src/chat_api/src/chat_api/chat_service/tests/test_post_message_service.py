from __future__ import annotations

from fastapi.testclient import TestClient

from slack_service.app import app, _SEEDED_MESSAGES


def test_post_message_returns_message_with_ts() -> None:
    client = TestClient(app)
    _SEEDED_MESSAGES.clear()
    payload = {"channel_id": "C001", "text": "hello"}
    resp = client.post("/messages", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel_id"] == "C001"
    assert data["text"] == "hello"
    assert isinstance(data["id"], str) and data["id"]
    assert isinstance(data["ts"], str) and data["ts"]


def test_list_messages_stub_respects_limit() -> None:
    client = TestClient(app)
    _SEEDED_MESSAGES.clear()

    for i in range(3):
        resp = client.post(
            "/messages",
            json={"channel_id": "C001", "text": f"msg-{i}"},
        )
        assert resp.status_code == 200

    resp = client.get("/channels/C001/messages", params={"limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert len(data["messages"]) == 2


def test_delete_message_removes_message() -> None:
    client = TestClient(app)
    _SEEDED_MESSAGES.clear()

    # Seed a message in C002
    resp = client.post(
        "/messages",
        json={"channel_id": "C002", "text": "to delete"},
    )
    assert resp.status_code == 200
    msg = resp.json()
    message_id = msg["id"]

    # Ensure it appears in the channel history
    resp = client.get("/channels/C002/messages")
    assert resp.status_code == 200
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert message_id in ids

    # Delete it
    resp = client.delete(f"/channels/C002/messages/{message_id}")
    assert resp.status_code == 204

    # Confirm it is gone
    resp = client.get("/channels/C002/messages")
    assert resp.status_code == 200
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert message_id not in ids


def test_list_all_messages_aggregates_channels() -> None:
    client = TestClient(app)
    _SEEDED_MESSAGES.clear()

    resp = client.post(
        "/messages",
        json={"channel_id": "C001", "text": "c1-message"},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/messages",
        json={"channel_id": "C002", "text": "c2-message"},
    )
    assert resp.status_code == 200

    resp = client.get("/messages")
    assert resp.status_code == 200
    data = resp.json()
    channels = {m["channel_id"] for m in data["messages"]}
    assert "C001" in channels
    assert "C002" in channels
