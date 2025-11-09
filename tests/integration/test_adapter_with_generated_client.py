"""Integration test: adapter talking to the local FastAPI service in-process.

This test uses FastAPI's TestClient base_url (http://testserver). The adapter
detects this and routes requests in-process via httpx's ASGI transport.
"""

from __future__ import annotations

import base64
import secrets
from typing import NoReturn

import pytest
from openai_client_impl.response import get_conversation as build_conversation
from starlette import status

from openai_adapter import AdapterAPIError, OpenAIServiceAdapter
from openai_client_impl import MissingOpenAIKeyError
from openai_client_service.main import app
from openai_client_service.src.openai_client_service.dependencies import (
    create_session_for_testing,
    destroy_session_for_testing,
    get_ai_client,
)

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional dependency
    TestClient = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration

SESSION_BYTES = 24
EXPECTED_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED


def _require_test_client() -> TestClient:
    if TestClient is None:
        pytest.skip("fastapi test client is not installed in this environment")
    return TestClient


def test_adapter_end_to_end_against_app() -> None:
    """Start the FastAPI app and call it through the adapter using TestClient base URL."""
    test_client_cls = _require_test_client()
    test_client = test_client_cls(app)
    base_url = str(test_client.base_url)

    test_subject = "it-user"
    session_id = base64.urlsafe_b64encode(secrets.token_bytes(SESSION_BYTES)).decode().rstrip("=")
    create_session_for_testing(session_id, test_subject)
    fake_client = _FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_client  # type: ignore[misc]

    adapter = OpenAIServiceAdapter(base_url=base_url, session_id=session_id)

    try:
        assert adapter.health_check() is True

        conv_id = adapter.create_conversation()
        assert isinstance(conv_id, str)
        assert conv_id

        data = adapter.get_conversation(conv_id)
        assert data.get("id") == conv_id

        assert adapter.delete_conversation(conv_id) is True

        with pytest.raises(AdapterAPIError) as exc_info:
            adapter.generate_response(["hello there"], conversation_id=None)
        assert exc_info.value.status_code == EXPECTED_UNAUTHORIZED
    finally:
        destroy_session_for_testing(session_id)
        app.dependency_overrides.pop(get_ai_client, None)


class _FakeAIClient:
    """Test double for the AI client used by the service."""

    def __init__(self) -> None:
        self._conv_id = "conv-1"
        self._messages: list[tuple[str, str]] = [("user", "hi")]
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

    def generate_response(
        self,
        messages: list[str],
        *,
        conversation_id: str | None = None,
    ) -> NoReturn:
        """Raise MissingOpenAIKeyError to simulate missing credentials."""
        _ = messages, conversation_id
        message = "No API key set"
        raise MissingOpenAIKeyError(message)
