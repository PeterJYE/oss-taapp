from __future__ import annotations

from fastapi.testclient import TestClient

from slack_service.app import app


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"ok": True}
