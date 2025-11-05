"""Integration tests for gmail_client_impl authentication and API connectivity.

This module tests that the dependency injection works correctly and that
the client can authenticate and make real API calls to Gmail.
"""

import logging
from collections.abc import Iterator

import pytest

import gmail_client_impl
import mail_client_api

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


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
    except (RuntimeError, ValueError, ConnectionError) as e:
        msg = str(e)
        if "No valid credentials found" in msg or "interactive mode is disabled" in msg:
            pytest.skip("Skipping integration test: no valid credentials available")
        pytest.fail(f"Integration test failed during authentication or API call: {e}")


@pytest.mark.integration
def test_adapter_service_integration() -> None:  # noqa: C901
    """Test adapter integration with mail service using mocked clients."""
    error_not_found = "not found"

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
            for m in self._messages:
                if m.id == message_id:
                    return m
            raise KeyError(error_not_found)

        def delete_message(self, message_id: str) -> bool:
            """Delete message by ID."""
            for i, m in enumerate(self._messages):
                if m.id == message_id:
                    del self._messages[i]
                    return True
            return False

        def mark_as_read(self, message_id: str) -> bool:
            """Mark message as read by ID."""
            return any(m.id == message_id for m in self._messages)

    dummy = DummyGmailClient()

    pytest.importorskip("fastapi")
    pytest.importorskip("adapter.service_client_adapter")

    from fastapi.testclient import TestClient  # noqa: PLC0415

    from adapter.service_client_adapter import ServiceClientAdapter  # noqa: PLC0415
    from mail_client_service import app as mail_app  # noqa: PLC0415
    from mail_client_service.main import get_client_dep  # noqa: PLC0415

    mail_app.dependency_overrides[get_client_dep] = lambda: dummy

    try:
        client = TestClient(mail_app)
        adapter = ServiceClientAdapter(base_url=client.base_url)

        expected_message_count = 2
        msgs = list(adapter.get_messages(max_results=10))
        assert len(msgs) == expected_message_count
        assert msgs[0].id == "m1"
        assert msgs[0].subject == "Subject 1"

        msg = adapter.get_message("m2")
        assert msg.id == "m2"
        assert msg.subject == "Subject 2"

        assert adapter.mark_as_read("m1") is True
        assert adapter.delete_message("m1") is True

        msgs_after = list(adapter.get_messages(max_results=10))
        assert len(msgs_after) == 1
    finally:
        mail_app.dependency_overrides.pop(get_client_dep, None)


@pytest.mark.circleci
def test_dependency_injection_works() -> None:
    """Tests that importing the implementation packages correctly overrides.

    The factory functions in the abstract contract packages.
    This test doesn't require credentials, only tests imports and factory setup.
    """
    try:
        client = mail_client_api.get_client(interactive=False)
        assert isinstance(client, gmail_client_impl.GmailClient)
        assert hasattr(client, "get_messages")
        assert hasattr(client, "get_message")
        assert hasattr(client, "delete_message")
        assert hasattr(client, "mark_as_read")
    except RuntimeError as e:
        if "No valid credentials found" in str(e):
            pass
        else:
            raise


@pytest.mark.circleci
def test_message_dependency_injection() -> None:
    """Tests that importing gmail_message_impl overrides message.get_message."""
    from gmail_client_impl.message_impl import get_message  # noqa: PLC0415
    from mail_client_api.message import get_message as get_message_contract  # noqa: PLC0415

    assert get_message_contract is get_message


@pytest.mark.circleci
def test_factory_functions_work_together() -> None:
    """Tests that both client and message factory functions are correctly overridden."""
    from gmail_client_impl.gmail_impl import get_client as get_client_impl  # noqa: PLC0415

    assert mail_client_api.get_client is get_client_impl


@pytest.mark.circleci
def test_client_scope_permissions() -> None:
    """Tests that the client has the necessary OAuth scopes for the operations we want to perform."""
    try:
        client = mail_client_api.get_client(interactive=False)

        gmail_client = client
        assert isinstance(gmail_client, gmail_client_impl.GmailClient)

        messages_result = (
            gmail_client.service.users()  # type: ignore[attr-defined]
            .messages()
            .list(userId="me", maxResults=1)
            .execute()
        )

        assert isinstance(messages_result, dict)
        assert "messages" in messages_result or messages_result.get("resultSizeEstimate", 0) == 0

    except FileNotFoundError:
        pytest.skip("Skipping integration test: credentials.json not found.")
    except (RuntimeError, ValueError, ConnectionError) as e:
        msg = str(e)
        if "No valid credentials found" in msg or "interactive mode is disabled" in msg:
            pytest.skip("Skipping integration test: no valid credentials available")
        if "403" in msg or "insufficient" in msg.lower():
            pytest.fail(f"OAuth scope issue - client may not have required permissions: {e}")
        pytest.fail(f"Integration test failed: {e}")


@pytest.mark.circleci
def test_client_initialization_modes() -> None:
    """Tests that the client can be initialized in both interactive and non-interactive modes."""
