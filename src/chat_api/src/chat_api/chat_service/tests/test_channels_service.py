from __future__ import annotations

from fastapi.testclient import TestClient

from slack_service.app import app


def test_list_channels_returns_two_expected() -> None:
    client = TestClient(app)
    resp = client.get("/channels")
    assert resp.status_code == 200
    data = resp.json()
    # Expect deterministic channels from SlackClient impl
    assert isinstance(data, list)
    ids = [c["id"] for c in data]
    assert ids == ["C001", "C002"]
    names = [c["name"] for c in data]
    assert all(isinstance(n, str) and n for n in names)
