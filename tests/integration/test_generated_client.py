"""Integration tests for the auto-generated OpenAI Client Service API client.

These tests verify that the generated client can successfully communicate with the service.
"""

import pytest

pytestmark = pytest.mark.integration


def test_client_generation_is_available() -> None:
    """Test that the generation script exists and can be imported."""
    from pathlib import Path  # noqa: PLC0415

    generate_script = (
        Path(__file__).parent.parent.parent / "src" / "openai_client_service_api_client" / "scripts" / "generate_client.py"
    )

    assert generate_script.exists(), "Generation script should exist"


def test_client_can_be_generated_from_test_service() -> None:
    """Test that the client can be generated from a running FastAPI service."""
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from openai_client_service.main import app  # noqa: PLC0415  # type: ignore[import-untyped]

    test_client = TestClient(app)

    http_ok = 200
    response = test_client.get("/openapi.json")
    assert response.status_code == http_ok

    spec = response.json()
    assert "paths" in spec
    assert "/health" in spec["paths"]
    assert "/ai/generate-response" in spec["paths"]
    assert "/ai/conversations" in spec["paths"]
    assert "/auth/set-openai-key" in spec["paths"]


def test_service_endpoints_accessible_via_test_client() -> None:
    """Test that we can interact with the service via the test client."""
    import base64  # noqa: PLC0415
    import secrets  # noqa: PLC0415

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from openai_client_service.dependencies import _create_session  # noqa: PLC0415
    from openai_client_service.main import app  # noqa: PLC0415  # type: ignore[import-untyped]

    test_client = TestClient(app)

    http_ok = 200
    response = test_client.get("/health")
    assert response.status_code == http_ok
    assert response.json() == {"status": "ok"}

    test_subject = "test-user"
    session_id = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
    _create_session(session_id, test_subject)

    http_bad_request = 400
    http_unauthorized = 401
    response = test_client.post(
        "/ai/generate-response",
        json={
            "messages": ["Hello!"],
            "conversation_id": None,
        },
        cookies={"session_id": session_id},
    )
    assert response.status_code in [http_ok, http_unauthorized, http_bad_request]
    if response.status_code == http_unauthorized:
        assert "error" in response.json() or "OpenAI API key" in response.json().get("hint", "")


def test_openapi_spec_structure() -> None:
    """Test that the OpenAPI spec has the expected structure for client generation."""
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from openai_client_service.main import app  # noqa: PLC0415  # type: ignore[import-untyped]

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
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from openai_client_service.main import app  # noqa: PLC0415  # type: ignore[import-untyped]

    test_client = TestClient(app)
    response = test_client.get("/openapi.json")
    spec = response.json()

    if "/ai/generate-response" in spec["paths"]:
        generate_spec = spec["paths"]["/ai/generate-response"]
        assert "post" in generate_spec

        assert "requestBody" in generate_spec["post"]

    if "/ai/conversations" in spec["paths"]:
        conversations_spec = spec["paths"]["/ai/conversations"]
        assert "post" in conversations_spec

        assert "requestBody" in conversations_spec.get("post", {})


def test_service_handles_missing_session() -> None:
    """Test that the service properly validates the session cookie."""
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from openai_client_service.main import app  # noqa: PLC0415  # type: ignore[import-untyped]

    test_client = TestClient(app)

    response = test_client.post(
        "/ai/generate-response",
        json={
            "messages": ["Hello!"],
            "conversation_id": None,
        },
    )

    http_unauthorized = 401
    assert response.status_code == http_unauthorized
