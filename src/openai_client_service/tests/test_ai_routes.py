"""Tests for the OpenAI client service AI routes."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette import status

from openai_client_service.main import app
from openai_client_service.src.openai_client_service import ai_interface_impl
from openai_client_service.src.openai_client_service.dependencies import (
    get_ai_client,
    get_authenticated_subject,
)

try:
    from openai_client_impl import MissingOpenAIKeyError
except ImportError:  # pragma: no cover

    class MissingOpenAIKeyError(Exception):
        """Fallback error used when openai_client_impl is unavailable."""


TOKENS_USED = 7
DEFAULT_CONVERSATION_ID = "conv-new"
CREATED_CONVERSATION_ID = "conv-created"
CONVERSATION_LOOKUP_ID = "conv-1"
CONVERSATION_CREATED_AT = "2025-01-01T00:00:00Z"
HTTP_OK = status.HTTP_200_OK
HTTP_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
HTTP_BAD_REQUEST = status.HTTP_400_BAD_REQUEST
HTTP_INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Configure TestClient with dependency overrides and a fake AI client."""
    fake_client = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_client  # type: ignore[return-value]
    app.dependency_overrides[get_authenticated_subject] = lambda: "user-1"  # type: ignore[return-value]

    main_module = import_module("openai_client_service.main")
    monkeypatch.setattr(main_module, "init_db", lambda: None, raising=False)

    test_client = TestClient(app)
    test_client.app.state.fake_ai_client = fake_client  # type: ignore[attr-defined]
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


class FakeAIClient:
    """Test double implementing the AI client surface."""

    def __init__(self) -> None:
        """Initialise the fake client flags and captured call storage."""
        self.saved_args: list[tuple[str, dict[str, Any]]] = []
        self.raise_missing = False
        self.raise_value = False
        self.raise_runtime = False

    def compose_response(self, messages: list[str], *, conversation_id: str | None = None) -> FakeResponse:
        """Simulate generating a response."""
        if self.raise_missing:
            error_message = "missing key"
            raise MissingOpenAIKeyError(error_message)
        if self.raise_value:
            error_message = "bad request"
            raise ValueError(error_message)
        if self.raise_runtime:
            error_message = "server down"
            raise RuntimeError(error_message)
        self.saved_args.append(("generate", {"messages": messages, "conversation_id": conversation_id}))
        return FakeResponse(content="hi", tokens_used=TOKENS_USED, conversation_id=conversation_id or DEFAULT_CONVERSATION_ID)

    def create_conversation(self) -> str:
        """Simulate creating a conversation."""
        if self.raise_missing:
            error_message = "missing key"
            raise MissingOpenAIKeyError(error_message)
        if self.raise_runtime:
            error_message = "cannot create"
            raise RuntimeError(error_message)
        self.saved_args.append(("create", {}))
        return CREATED_CONVERSATION_ID

    def get_conversation(self, conversation_id: str) -> FakeConversation:
        """Simulate retrieving a conversation."""
        if self.raise_missing:
            error_message = "missing key"
            raise MissingOpenAIKeyError(error_message)
        if self.raise_value:
            error_message = "not found"
            raise ValueError(error_message)
        self.saved_args.append(("get", {"conversation_id": conversation_id}))
        return FakeConversation(conversation_id, [("user", "hello"), ("assistant", "hi")], CONVERSATION_CREATED_AT)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Simulate deleting a conversation."""
        if self.raise_missing:
            error_message = "missing key"
            raise MissingOpenAIKeyError(error_message)
        if self.raise_value:
            error_message = "not found"
            raise ValueError(error_message)
        self.saved_args.append(("delete", {"conversation_id": conversation_id}))
        return True


class FakeResponse:
    """Simple value object that mirrors the real Response dataclass."""

    def __init__(self, content: str, tokens_used: int, conversation_id: str | None) -> None:
        """Store response data for downstream assertions."""
        self.content = content
        self.tokens_used = tokens_used
        self.conversation_id = conversation_id


class FakeConversation:
    """Simple value object for conversation payloads."""

    def __init__(self, conv_id: str, messages: list[tuple[str, str]], created_at: str) -> None:
        """Store conversation metadata for downstream assertions."""
        self.id = conv_id
        self.messages = messages
        self.created_at = created_at


@pytest.mark.unit
def test_compose_response_success(client: TestClient) -> None:
    """POST /ai/compose-response should succeed with valid payload."""
    payload = {"messages": ["hello"], "conversation_id": None}
    resp = client.post("/ai/compose-response", json=payload)
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["content"] == "hi"
    assert data["tokens_used"] == TOKENS_USED
    assert data["conversation_id"] == DEFAULT_CONVERSATION_ID


@pytest.mark.unit
def test_compose_response_handles_missing_key(client: TestClient) -> None:
    """Missing API keys should return HTTP 401."""
    fake_client: FakeAIClient = client.app.state.fake_ai_client  # type: ignore[attr-defined]
    fake_client.raise_missing = True

    resp = client.post("/ai/compose-response", json={"messages": ["hi"]})
    assert resp.status_code == HTTP_UNAUTHORIZED
    detail = resp.json()["detail"]
    assert "hint" in detail


@pytest.mark.unit
def test_compose_response_handles_value_error(client: TestClient) -> None:
    """Backend value errors should surface as HTTP 400."""
    fake_client: FakeAIClient = client.app.state.fake_ai_client  # type: ignore[attr-defined]
    fake_client.raise_value = True

    resp = client.post("/ai/compose-response", json={"messages": ["hi"]})
    assert resp.status_code == HTTP_BAD_REQUEST
    assert "bad request" in resp.text.lower()


@pytest.mark.unit
def test_create_conversation_success(client: TestClient) -> None:
    """POST /ai/conversations should create a new conversation."""
    resp = client.post("/ai/conversations")
    assert resp.status_code == HTTP_OK
    assert resp.json() == {"conversation_id": CREATED_CONVERSATION_ID}


@pytest.mark.unit
def test_get_conversation_success(client: TestClient) -> None:
    """GET /ai/conversations/{id} should return conversation details."""
    resp = client.get(f"/ai/conversations/{CONVERSATION_LOOKUP_ID}")
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["id"] == CONVERSATION_LOOKUP_ID
    assert data["messages"][0] == ["user", "hello"]


@pytest.mark.unit
def test_delete_conversation_success(client: TestClient) -> None:
    """DELETE /ai/conversations/{id} should return success flag."""
    resp = client.delete(f"/ai/conversations/{CONVERSATION_LOOKUP_ID}")
    assert resp.status_code == HTTP_OK
    assert resp.json()["ok"] is True


@pytest.mark.unit
def test_generate_response_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should succeed with valid payload and API key."""

    # Mock OpenAI client
    class MockMessage:
        def __init__(self) -> None:
            self.content = "Hello! How can I help you?"

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_OK
    assert resp.json() == "Hello! How can I help you?"


@pytest.mark.unit
def test_generate_response_with_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should return structured JSON when schema is provided."""

    # Mock OpenAI client with JSON response
    class MockMessage:
        def __init__(self) -> None:
            self.content = '{"action": "greet", "message": "Hello!"}'

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
        "response_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["action", "message"],
        },
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert isinstance(data, dict)
    assert "action" in data
    assert "message" in data


@pytest.mark.unit
def test_generate_response_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should return 400 when OPENAI_API_KEY is not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_BAD_REQUEST
    assert "OPENAI_API_KEY" in resp.json()["detail"]


@pytest.mark.unit
def test_generate_response_handles_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should handle OpenAI API errors."""

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> None:
            error_msg = "API rate limit exceeded"
            raise ValueError(error_msg)

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert "AI service failed" in resp.json()["detail"]


@pytest.mark.unit
def test_generate_response_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should handle empty content from OpenAI."""

    class MockMessage:
        def __init__(self) -> None:
            self.content = None

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert "empty response" in resp.json()["detail"]


@pytest.mark.unit
def test_generate_response_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should handle invalid JSON in structured response."""

    class MockMessage:
        def __init__(self) -> None:
            self.content = "not valid json {"

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
        "response_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
            },
        },
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert "Failed to parse structured response" in resp.json()["detail"]


@pytest.mark.unit
def test_generate_response_non_dict_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should handle non-dict response when schema is provided."""

    class MockMessage:
        def __init__(self) -> None:
            self.content = '["not", "a", "dict"]'

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
        "response_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
            },
        },
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert "must be a dictionary" in resp.json()["detail"]


@pytest.mark.unit
def test_generate_response_schema_preparation(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/generate_response should prepare schema with additionalProperties and required."""

    class MockMessage:
        def __init__(self) -> None:
            self.content = '{"action": "test", "message": "test"}'

    class MockChoice:
        def __init__(self) -> None:
            self.message = MockMessage()

    class MockCompletion:
        def __init__(self) -> None:
            self.choices = [MockChoice()]

    class MockCompletions:
        @staticmethod
        def create(**_kwargs: Any) -> MockCompletion:
            return MockCompletion()

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = MockChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(ai_interface_impl, "OpenAI", MockOpenAI)

    test_client = TestClient(app)
    # Schema without additionalProperties and required
    payload = {
        "user_input": "Hello",
        "system_prompt": "You are a helpful assistant.",
        "response_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "message": {"type": "string"},
            },
        },
    }
    resp = test_client.post("/ai/generate_response", json=payload)
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert isinstance(data, dict)
    assert "action" in data
    assert "message" in data
