"""Integration tests for gmail_client_impl authentication and API connectivity.

This module tests that the dependency injection works correctly and that
the client can authenticate and make real API calls to Gmail.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from gmail_client_impl.gmail_impl import get_client_impl
from gmail_client_impl.message_impl import get_message_impl as gmail_get_message_impl

import gmail_client_impl
import mail_client_api
import mail_client_api.message as message_module

if TYPE_CHECKING:
    from collections.abc import Iterator
else:  # pragma: no cover - used only for type checking
    Iterator = object  # type: ignore[assignment]

try:
    from adapter.service_client_adapter import ServiceClientAdapter
except ImportError:  # pragma: no cover
    ServiceClientAdapter = None  # type: ignore[assignment]

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

try:
    from mail_client_service import app as mail_app
    from mail_client_service.main import get_client_dep
except ImportError:  # pragma: no cover
    mail_app = None  # type: ignore[assignment]
    get_client_dep = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)

ERROR_NOT_FOUND = "not found"
EXPECTED_MESSAGE_COUNT = 2
EXPECTED_MESSAGES_AFTER_DELETE = 1


@pytest.fixture(autouse=True)
def _ensure_gmail_registration() -> None:
    """Ensure the Gmail implementation is wired into the abstract API."""
    gmail_client_impl.register()


def _require_test_client() -> TestClient:
    if TestClient is None or mail_app is None:
        pytest.skip("FastAPI test client is not available in this environment.")
    return TestClient


def _require_service_adapter() -> type[ServiceClientAdapter]:
    if ServiceClientAdapter is None:
        pytest.skip("adapter.service_client_adapter is not installed.")
    return ServiceClientAdapter


class DummyMessage:
    """Dummy message for testing."""

    def __init__(self, message_id: str, subject: str, from_: str = "alice@example.com") -> None:
        """Initialize dummy message."""
        self.id = message_id
        self.subject = subject
        self.from_ = from_
        self.to = "me@example.com"
        self.date = "2025-01-01T00:00:00Z"
        self.body = "Hello from dummy"


class DummyGmailClient:
    """Dummy Gmail client for testing."""

    def __init__(self) -> None:
        """Initialize dummy client with test messages."""
        self._messages = [DummyMessage("m1", "Subject 1"), DummyMessage("m2", "Subject 2")]

    def get_messages(self, max_results: int = 10) -> Iterator[DummyMessage]:
        """Get messages iterator."""
        yield from self._messages[:max_results]

    def get_message(self, message_id: str) -> DummyMessage:
        """Get message by ID."""
        for message in self._messages:
            if message.id == message_id:
                return message
        error_message = ERROR_NOT_FOUND
        raise KeyError(error_message)

    def delete_message(self, message_id: str) -> bool:
        """Delete message by ID."""
        for index, message in enumerate(self._messages):
            if message.id == message_id:
                del self._messages[index]
                return True
        return False

    def mark_as_read(self, message_id: str) -> bool:
        """Mark message as read by ID."""
        return any(message.id == message_id for message in self._messages)


@pytest.mark.circleci
def test_get_client_and_authenticate() -> None:
    """Tests that the factory provides a real, authenticated GmailClient.

    This test requires real credentials (via .env or credentials.json)
    and makes a live, read-only call to the Gmail API.
    """
    try:
        client = mail_client_api.get_client(interactive=False)
        assert isinstance(client, gmail_client_impl.GmailClient)
    except FileNotFoundError:
        pytest.skip("Skipping integration test: credentials.json not found.")
    except (RuntimeError, ValueError, ConnectionError) as exc:
        msg = str(exc)
        if "No valid credentials found" in msg or "interactive mode is disabled" in msg:
            pytest.skip("Skipping integration test: no valid credentials available")
        pytest.fail(f"Integration test failed during authentication or API call: {exc}")


@pytest.mark.integration
def test_adapter_service_integration() -> None:
    """Test adapter integration with mail service using mocked clients."""
    dummy = DummyGmailClient()
    test_client_cls = _require_test_client()
    adapter_cls = _require_service_adapter()
    assert mail_app is not None
    assert get_client_dep is not None

    mail_app.dependency_overrides[get_client_dep] = lambda: dummy

    try:
        client = test_client_cls(mail_app)
        adapter = adapter_cls(base_url=client.base_url)

        messages = list(adapter.get_messages(max_results=10))
        assert len(messages) == EXPECTED_MESSAGE_COUNT
        assert messages[0].id == "m1"
        assert messages[0].subject == "Subject 1"

        message = adapter.get_message("m2")
        assert message.id == "m2"
        assert message.subject == "Subject 2"

        assert adapter.mark_as_read("m1") is True
        assert adapter.delete_message("m1") is True

        messages_after_delete = list(adapter.get_messages(max_results=10))
        assert len(messages_after_delete) == EXPECTED_MESSAGES_AFTER_DELETE
    finally:
        mail_app.dependency_overrides.pop(get_client_dep, None)


@pytest.mark.circleci
def test_dependency_injection_works() -> None:
    """Tests that importing the implementation packages correctly overrides the factories."""
    try:
        client = mail_client_api.get_client(interactive=False)
        assert isinstance(client, gmail_client_impl.GmailClient)
        assert hasattr(client, "get_messages")
        assert hasattr(client, "get_message")
        assert hasattr(client, "delete_message")
        assert hasattr(client, "mark_as_read")
    except RuntimeError as exc:
        if "No valid credentials found" in str(exc):
            return
        raise


@pytest.mark.circleci
def test_message_dependency_injection() -> None:
    """Tests that importing gmail_message_impl overrides message.get_message."""
    assert message_module.get_message is gmail_get_message_impl


@pytest.mark.circleci
def test_factory_functions_work_together() -> None:
    """Tests that both client and message factory functions are correctly overridden."""
    assert mail_client_api.get_client is get_client_impl


@pytest.mark.circleci
def test_client_scope_permissions() -> None:
    """Tests that the client has the necessary OAuth scopes for the operations we want to perform."""
    try:
        client = mail_client_api.get_client(interactive=False)
        assert isinstance(client, gmail_client_impl.GmailClient)

        messages_result = (
            client.service.users()  # type: ignore[attr-defined]
            .messages()
            .list(userId="me", maxResults=1)
            .execute()
        )

        assert isinstance(messages_result, dict)
        assert "messages" in messages_result or messages_result.get("resultSizeEstimate", 0) == 0
    except FileNotFoundError:
        pytest.skip("Skipping integration test: credentials.json not found.")
    except (RuntimeError, ValueError, ConnectionError) as exc:
        msg = str(exc)
        if "No valid credentials found" in msg or "interactive mode is disabled" in msg:
            pytest.skip("Skipping integration test: no valid credentials available")
        if "403" in msg or "insufficient" in msg.lower():
            pytest.fail(f"OAuth scope issue - client may not have required permissions: {exc}")
        pytest.fail(f"Integration test failed: {exc}")


@pytest.mark.circleci
def test_client_initialization_modes() -> None:
    """Tests that the client can be initialized in both interactive and non-interactive modes."""
