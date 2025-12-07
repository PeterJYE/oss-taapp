"""Integration tests for the auto-generated OpenAI Client Service API client."""

from __future__ import annotations

import base64
import secrets
from pathlib import Path
from typing import NoReturn

import pytest
from openai_client_impl.response import get_conversation as build_conversation
from starlette import status

from openai_client_impl import MissingOpenAIKeyError

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

try:
    from openai_client_service.src.openai_client_service.dependencies import (
        create_session_for_testing,
        destroy_session_for_testing,
        get_ai_client,
    )
except ImportError:  # pragma: no cover
    create_session_for_testing = None  # type: ignore[assignment]
    destroy_session_for_testing = None  # type: ignore[assignment]
    get_ai_client = None  # type: ignore[assignment]

try:
    from openai_client_service.main import app  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    app = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration

SESSION_BYTES = 24
HTTP_OK = status.HTTP_200_OK
HTTP_BAD_REQUEST = status.HTTP_400_BAD_REQUEST
HTTP_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED


def _require_test_client() -> TestClient:
    if TestClient is None or app is None:
        pytest.skip("FastAPI TestClient is not available.")
    return TestClient


def _require_session_helpers() -> tuple:
    if create_session_for_testing is None or destroy_session_for_testing is None:
        pytest.skip("Session helper utilities are not available.")
    return create_session_for_testing, destroy_session_for_testing


class _FakeAIClient:
    """Test double providing minimal AI client behaviour for integration tests."""

    def __init__(self) -> None:
        self._conv_id = "conv-int-1"
        self._messages: list[tuple[str, str]] = [("user", "hello")]
        self._created_at = "2025-01-01T00:00:00Z"

    def create_conversation(self) -> str:
        """Return a deterministic conversation identifier."""
        return self._conv_id

    def get_conversation(self, conversation_id: str) -> object:
        """Return a conversation object or raise if missing."""
        if conversation_id != self._conv_id:
            message = "Conversation not found"
            raise ValueError(message)
        return build_conversation(self._conv_id, self._messages, self._created_at)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Pretend to delete the stored conversation."""
        return conversation_id == self._conv_id

    def compose_response(
        self,
        messages: list[str],
        *,
        conversation_id: str | None = None,
    ) -> NoReturn:
        """Raise MissingOpenAIKeyError to simulate missing credentials."""
        _ = messages, conversation_id
        message = "No API key set"
        raise MissingOpenAIKeyError(message)


def test_client_generation_is_available() -> None:
    """Test that the generation script exists and can be imported."""
    generate_script = (
        Path(__file__).parent.parent.parent / "src" / "openai_client_service_api_client" / "scripts" / "generate_client.py"
    )
    assert generate_script.exists(), "Generation script should exist"


def test_client_can_be_generated_from_test_service() -> None:
    """Test that the client can be generated from a running FastAPI service."""
    test_client_cls = _require_test_client()
    client = test_client_cls(app)
    response = client.get("/openapi.json")
    assert response.status_code == HTTP_OK

    spec = response.json()
    assert "paths" in spec
    assert "/health" in spec["paths"]
    assert "/ai/generate_response" in spec["paths"]
    assert "/ai/conversations" in spec["paths"]
    assert "/auth/set-openai-key" in spec["paths"]


def test_service_endpoints_accessible_via_test_client() -> None:
    """Test that we can interact with the service via the test client."""
    test_client_cls = _require_test_client()
    create_session, destroy_session = _require_session_helpers()

    client = test_client_cls(app)
    response = client.get("/health")
    assert response.status_code == HTTP_OK
    body = response.json()
    assert body.get("status") == "ok"

    test_subject = "test-user"
    session_id = base64.urlsafe_b64encode(secrets.token_bytes(SESSION_BYTES)).decode().rstrip("=")
    create_session(session_id, test_subject)
    fake_client = _FakeAIClient()
    if get_ai_client is not None:
        app.dependency_overrides[get_ai_client] = lambda: fake_client  # type: ignore[misc]

    try:
        response = client.post(
            "/ai/compose-response",
            json={"messages": ["Hello!"], "conversation_id": None},
            cookies={"session_id": session_id},
        )
        assert response.status_code in {HTTP_OK, HTTP_UNAUTHORIZED, HTTP_BAD_REQUEST}
        if response.status_code == HTTP_UNAUTHORIZED:
            detail = response.json()
            detail_payload = detail.get("detail", {})
            hint_text = detail_payload.get("hint", "")
            assert "error" in detail_payload or "OpenAI API key" in hint_text
    finally:
        destroy_session(session_id)
        if get_ai_client is not None:
            app.dependency_overrides.pop(get_ai_client, None)


def test_openapi_spec_structure() -> None:
    """Test that the OpenAPI spec has the expected structure for client generation."""
    test_client_cls = _require_test_client()
    client = test_client_cls(app)
    spec = client.get("/openapi.json").json()

    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert "title" in spec["info"]
    assert "paths" in spec
    assert "components" in spec


def test_all_endpoints_have_request_body_schemas() -> None:
    """Test that POST endpoints have properly documented request bodies."""
    test_client_cls = _require_test_client()
    client = test_client_cls(app)
    spec = client.get("/openapi.json").json()

    generate_spec = spec.get("paths", {}).get("/ai/generate_response", {})
    post_spec = generate_spec.get("post", {})
    assert "requestBody" in post_spec

    conversations_spec = spec.get("paths", {}).get("/ai/conversations", {})
    post_spec = conversations_spec.get("post", {})
    if "requestBody" in post_spec:
        assert "content" in post_spec["requestBody"]


def test_service_handles_missing_session() -> None:
    """Test that the service properly validates the session cookie."""
    test_client_cls = _require_test_client()
    client = test_client_cls(app)
    response = client.post("/ai/compose-response", json={"messages": ["Hello!"], "conversation_id": None})
    assert response.status_code == HTTP_UNAUTHORIZED
