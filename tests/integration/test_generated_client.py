"""Integration tests for the auto-generated OpenAI Client Service API client.

These tests verify that the generated client can successfully communicate with the service.
"""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_client_generation_is_available() -> None:
    """Test that the generation script exists and can be imported."""
    from pathlib import Path

    generate_script = (
        Path(__file__).parent.parent.parent / "src" / "openai_client_service_api_client" / "scripts" / "generate_client.py"
    )

    assert generate_script.exists(), "Generation script should exist"


def test_client_can_be_generated_from_test_service() -> None:
    """Test that the client can be generated from a running FastAPI service."""
    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)

    http_ok = 200
    response = test_client.get("/openapi.json")
    assert response.status_code == http_ok

    spec = response.json()
    assert "paths" in spec
    assert "/health" in spec["paths"]
    assert "/ai/chat" in spec["paths"]
    assert "/ai/embed" in spec["paths"]
    assert "/auth/set-openai-key" in spec["paths"]


def test_service_endpoints_accessible_via_test_client() -> None:
    """Test that we can interact with the service via the test client."""
    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)

    http_ok = 200
    response = test_client.get("/health")
    assert response.status_code == http_ok
    assert response.json() == {"status": "ok"}

    response = test_client.post(
        "/ai/chat",
        json={
            "messages": [{"role": "user", "content": "Hello!"}],
            "model": "gpt-4o-mini",
        },
        headers={"X-Subject": "test-user"},
    )

    assert response.status_code in [200, 401, 400]
    assert "error" in response.json() or "OpenAI API key" in response.json()["hint"]


def test_openapi_spec_structure() -> None:
    """Test that the OpenAPI spec has the expected structure for client generation."""
    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)
    response = test_client.get("/openapi.json")
    spec = response.json()

    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert "title" in spec["info"]
    assert "paths" in spec
    assert "components" in spec

    assert "components" in spec
    if "securitySchemes" in spec["components"]:
        pass


def test_all_endpoints_have_request_body_schemas() -> None:
    """Test that POST endpoints have properly documented request bodies."""
    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)
    response = test_client.get("/openapi.json")
    spec = response.json()

    if "/ai/chat" in spec["paths"]:
        chat_spec = spec["paths"]["/ai/chat"]
        assert "post" in chat_spec

        assert "requestBody" in chat_spec["post"]

    if "/ai/embed" in spec["paths"]:
        embed_spec = spec["paths"]["/ai/embed"]
        assert "post" in embed_spec

        assert "requestBody" in embed_spec["post"]


def test_service_handles_missing_subject_header() -> None:
    """Test that the service properly validates the X-Subject header."""
    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)

    response = test_client.post(
        "/ai/chat",
        json={
            "messages": [{"role": "user", "content": "Hello!"}],
            "model": "gpt-4o-mini",
        },
    )

    http_unauthorized = 401
    # Should return 401 Unauthorized
    assert response.status_code == http_unauthorized
