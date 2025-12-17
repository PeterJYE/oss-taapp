from __future__ import annotations

from fastapi.testclient import TestClient

from slack_service.app import app


def test_openapi_available_and_has_paths() -> None:
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    doc = resp.json()
    assert "openapi" in doc
    assert "/health" in doc["paths"]
    assert "/channels" in doc["paths"]
    assert "/messages" in doc["paths"]
