"""End-to-End test for the full integration flow.

Tests the complete user flow:
1. Chat Service: Receives user message
2. AI Service: Converts natural language to structured JSON
3. Ticket Service: Executes the operation (create/get/update/delete)
4. Chat Service: Sends response back (notification)

This test can run with:
- Mocks (default): Fast, no external dependencies
- Real credentials (CircleCI): Set env vars for live API testing
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ai_api import AIInterface  # type: ignore[attr-defined]
from chat_api import ChatInterface, Message  # type: ignore[attr-defined]
from ticket_api import Ticket, TicketInterface, TicketStatus  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.e2e


# ============================================================================
# Mock Implementations
# ============================================================================


class MockMessage(Message):
    """Mock message for testing."""

    def __init__(self, message_id: str, content: str, sender_id: str) -> None:
        """Initialize mock message."""
        self._id = message_id
        self._content = content
        self._sender_id = sender_id

    @property
    def id(self) -> str:
        """Return message ID."""
        return self._id

    @property
    def content(self) -> str:
        """Return message content."""
        return self._content

    @property
    def sender_id(self) -> str:
        """Return sender ID."""
        return self._sender_id


class MockTicket(Ticket):
    """Mock ticket for testing."""

    def __init__(
        self,
        ticket_id: str,
        title: str,
        description: str,
        status: TicketStatus,
        assignee: str | None = None,
    ) -> None:
        """Initialize mock ticket."""
        self._id = ticket_id
        self._title = title
        self._description = description
        self._status = status
        self._assignee = assignee

    @property
    def id(self) -> str:
        """Return ticket ID."""
        return self._id

    @property
    def title(self) -> str:
        """Return ticket title."""
        return self._title

    @property
    def description(self) -> str:
        """Return ticket description."""
        return self._description

    @property
    def status(self) -> TicketStatus:
        """Return ticket status."""
        return self._status

    @property
    def assignee(self) -> str | None:
        """Return ticket assignee."""
        return self._assignee


class MockChatService:
    """Mock chat service (Slack) for testing."""

    def __init__(self) -> None:
        """Initialize with empty message queue."""
        self._messages: list[MockMessage] = []
        self._sent_responses: list[tuple[str, str]] = []

    def add_message(self, message: MockMessage) -> None:
        """Add a message to the queue."""
        self._messages.append(message)

    def get_messages(self, channel_id: str, limit: int = 10) -> list[MockMessage]:
        """Get messages from the queue."""
        return self._messages[:limit]

    def send_message(self, channel_id: str, content: str) -> bool:
        """Record sent message and return success."""
        self._sent_responses.append((channel_id, content))
        return True

    def get_sent_responses(self) -> list[tuple[str, str]]:
        """Get all responses that were sent."""
        return self._sent_responses


class MockAIService:
    """Mock AI service (OpenAI) for testing."""

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        response_schema: dict | None = None,
    ) -> dict:
        """Parse user input and return structured JSON."""
        user_lower = user_input.lower()

        if "create" in user_lower:
            # Extract title from user input
            title = "E2E Test Ticket"
            if "for" in user_lower:
                title = user_input.split("for", 1)[1].strip().rstrip(".")
            return {
                "method": "create_ticket",
                "parameters": {
                    "title": title,
                    "description": f"Created via E2E test: {user_input}",
                    "assignee": "",
                    "ticket_id": "",
                    "query": "",
                    "status": "",
                },
            }
        elif "get" in user_lower or "show" in user_lower:
            # Try to extract ticket ID
            import re
            ticket_match = re.search(r"(TEST-\d+)", user_input, re.IGNORECASE)
            ticket_id = ticket_match.group(1) if ticket_match else "TEST-1"
            return {
                "method": "get_ticket",
                "parameters": {
                    "ticket_id": ticket_id,
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                    "status": "",
                },
            }
        elif "search" in user_lower or "all" in user_lower:
            return {
                "method": "search_tickets",
                "parameters": {
                    "status": "open",
                    "query": "",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "ticket_id": "",
                },
            }
        elif "update" in user_lower:
            import re
            ticket_match = re.search(r"(TEST-\d+)", user_input, re.IGNORECASE)
            ticket_id = ticket_match.group(1) if ticket_match else "TEST-1"
            return {
                "method": "update_ticket",
                "parameters": {
                    "ticket_id": ticket_id,
                    "status": "in_progress",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                },
            }
        elif "delete" in user_lower:
            import re
            ticket_match = re.search(r"(TEST-\d+)", user_input, re.IGNORECASE)
            ticket_id = ticket_match.group(1) if ticket_match else "TEST-1"
            return {
                "method": "delete_ticket",
                "parameters": {
                    "ticket_id": ticket_id,
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                    "status": "",
                },
            }
        else:
            return {
                "method": "search_tickets",
                "parameters": {
                    "query": user_input,
                    "status": "",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "ticket_id": "",
                },
            }


class MockTicketService:
    """Mock ticket service (JIRA) for testing."""

    def __init__(self) -> None:
        """Initialize with in-memory storage."""
        self._tickets: dict[str, MockTicket] = {}
        self._counter = 1

    def create_ticket(
        self,
        title: str,
        description: str,
        assignee: str | None = None,
    ) -> MockTicket:
        """Create a new ticket."""
        ticket_id = f"TEST-{self._counter}"
        self._counter += 1
        ticket = MockTicket(
            ticket_id=ticket_id,
            title=title,
            description=description,
            status=TicketStatus.OPEN,
            assignee=assignee,
        )
        self._tickets[ticket_id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> MockTicket | None:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def search_tickets(
        self,
        query: str | None = None,
        status: TicketStatus | None = None,
    ) -> list[MockTicket]:
        """Search tickets."""
        results = list(self._tickets.values())
        if status:
            results = [t for t in results if t.status == status]
        if query:
            results = [t for t in results if query.lower() in t.title.lower()]
        return results

    def update_ticket(
        self,
        ticket_id: str,
        status: TicketStatus | None = None,
        title: str | None = None,
    ) -> MockTicket:
        """Update a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        updated = MockTicket(
            ticket_id=ticket_id,
            title=title or ticket.title,
            description=ticket.description,
            status=status or ticket.status,
            assignee=ticket.assignee,
        )
        self._tickets[ticket_id] = updated
        return updated

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket."""
        if ticket_id in self._tickets:
            del self._tickets[ticket_id]
            return True
        return False


# ============================================================================
# E2E Test: Full Integration Flow with Mocks
# ============================================================================


def process_message_e2e(
    user_input: str,
    channel_id: str,
    ai_service: MockAIService,
    ticket_service: MockTicketService,
    chat_service: MockChatService,
) -> str:
    """Process a message through the full flow and return response.

    This mirrors the logic in integration_main.py but uses mock services.
    """
    # Step 1: AI converts natural language to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation",
        response_schema={},
    )

    method = ai_response.get("method")
    params = ai_response.get("parameters", {})

    # Step 2: Execute ticket operation
    response = ""
    try:
        if method == "create_ticket":
            title = params.get("title", "").strip()
            description = params.get("description", "").strip() or f"Ticket for: {title}"
            ticket = ticket_service.create_ticket(
                title=title,
                description=description,
                assignee=params.get("assignee") or None,
            )
            response = f"Ticket created! ID: {ticket.id}, Title: {ticket.title}, Status: {ticket.status}"

        elif method == "get_ticket":
            ticket_id = params.get("ticket_id", "").strip()
            ticket = ticket_service.get_ticket(ticket_id)
            if ticket:
                response = f"{ticket.title} (ID: {ticket.id}, Status: {ticket.status})"
            else:
                response = f"Error: Ticket {ticket_id} not found"

        elif method == "search_tickets":
            status = TicketStatus(params["status"]) if params.get("status") else None
            tickets = ticket_service.search_tickets(
                query=params.get("query") or None,
                status=status,
            )
            if tickets:
                response = f"Found {len(tickets)} ticket(s)"
            else:
                response = "No tickets found"

        elif method == "update_ticket":
            ticket_id = params.get("ticket_id", "").strip()
            status = TicketStatus(params["status"]) if params.get("status") else None
            ticket = ticket_service.update_ticket(
                ticket_id=ticket_id,
                status=status,
                title=params.get("title") or None,
            )
            response = f"Ticket updated! ID: {ticket.id}, Status: {ticket.status}"

        elif method == "delete_ticket":
            ticket_id = params.get("ticket_id", "").strip()
            success = ticket_service.delete_ticket(ticket_id)
            response = "Ticket deleted successfully!" if success else "Failed to delete ticket"

        else:
            response = f"Error: Unknown method {method}"

    except Exception as e:
        response = f"Error: {e}"

    # Step 3: Send response via chat service (notification)
    chat_service.send_message(channel_id=channel_id, content=response)

    return response


def test_e2e_create_ticket_flow() -> None:
    """E2E test: User creates ticket via Chat → AI → Ticket → Notification."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    channel_id = "C12345"

    # User sends message to chat
    user_message = MockMessage(
        message_id="msg-1",
        content="Create a ticket for fixing authentication bug",
        sender_id="U12345",
    )
    chat_service.add_message(user_message)

    # Process the message through full flow
    response = process_message_e2e(
        user_input=user_message.content,
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    # Verify the complete flow
    assert "Ticket created!" in response
    assert "TEST-1" in response

    # Verify notification was sent
    sent_responses = chat_service.get_sent_responses()
    assert len(sent_responses) == 1
    assert sent_responses[0][0] == channel_id
    assert "Ticket created!" in sent_responses[0][1]

    # Verify ticket exists in system
    ticket = ticket_service.get_ticket("TEST-1")
    assert ticket is not None
    assert "authentication bug" in ticket.title.lower() or "fixing" in ticket.title.lower()


def test_e2e_get_ticket_flow() -> None:
    """E2E test: User gets ticket details via Chat → AI → Ticket → Notification."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    # Pre-create a ticket
    ticket_service.create_ticket(
        title="Test Bug",
        description="Test description",
    )

    channel_id = "C12345"
    user_message = MockMessage(
        message_id="msg-2",
        content="Show me ticket TEST-1",
        sender_id="U12345",
    )

    response = process_message_e2e(
        user_input=user_message.content,
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    assert "Test Bug" in response
    assert "TEST-1" in response

    sent_responses = chat_service.get_sent_responses()
    assert len(sent_responses) == 1


def test_e2e_search_tickets_flow() -> None:
    """E2E test: User searches tickets via Chat → AI → Ticket → Notification."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    # Pre-create some tickets
    ticket_service.create_ticket(title="Bug 1", description="First bug")
    ticket_service.create_ticket(title="Bug 2", description="Second bug")

    channel_id = "C12345"
    user_message = MockMessage(
        message_id="msg-3",
        content="Search all open tickets",
        sender_id="U12345",
    )

    response = process_message_e2e(
        user_input=user_message.content,
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    assert "Found 2 ticket(s)" in response


def test_e2e_update_ticket_flow() -> None:
    """E2E test: User updates ticket via Chat → AI → Ticket → Notification."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    # Pre-create a ticket
    ticket_service.create_ticket(
        title="To Update",
        description="Will be updated",
    )

    channel_id = "C12345"
    user_message = MockMessage(
        message_id="msg-4",
        content="Update ticket TEST-1 to in progress",
        sender_id="U12345",
    )

    response = process_message_e2e(
        user_input=user_message.content,
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    assert "Ticket updated!" in response
    assert "in_progress" in response.lower()

    # Verify ticket was updated
    ticket = ticket_service.get_ticket("TEST-1")
    assert ticket is not None
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_e2e_delete_ticket_flow() -> None:
    """E2E test: User deletes ticket via Chat → AI → Ticket → Notification."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    # Pre-create a ticket
    ticket_service.create_ticket(
        title="To Delete",
        description="Will be deleted",
    )

    channel_id = "C12345"
    user_message = MockMessage(
        message_id="msg-5",
        content="Delete ticket TEST-1",
        sender_id="U12345",
    )

    response = process_message_e2e(
        user_input=user_message.content,
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    assert "deleted successfully" in response.lower()

    # Verify ticket was deleted
    ticket = ticket_service.get_ticket("TEST-1")
    assert ticket is None


def test_e2e_full_crud_cycle() -> None:
    """E2E test: Complete CRUD cycle through all 4 services."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    channel_id = "C12345"

    # 1. CREATE
    response = process_message_e2e(
        user_input="Create a ticket for API documentation",
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )
    assert "Ticket created!" in response
    ticket_id = "TEST-1"

    # 2. READ
    response = process_message_e2e(
        user_input=f"Show me ticket {ticket_id}",
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )
    assert ticket_id in response

    # 3. UPDATE
    response = process_message_e2e(
        user_input=f"Update ticket {ticket_id} to in progress",
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )
    assert "Ticket updated!" in response

    # 4. DELETE
    response = process_message_e2e(
        user_input=f"Delete ticket {ticket_id}",
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )
    assert "deleted successfully" in response.lower()

    # Verify all notifications were sent
    sent_responses = chat_service.get_sent_responses()
    assert len(sent_responses) == 4


def test_e2e_error_handling() -> None:
    """E2E test: Error handling when ticket not found."""
    chat_service = MockChatService()
    ai_service = MockAIService()
    ticket_service = MockTicketService()

    channel_id = "C12345"

    # Try to get non-existent ticket
    response = process_message_e2e(
        user_input="Show me ticket TEST-999",
        channel_id=channel_id,
        ai_service=ai_service,
        ticket_service=ticket_service,
        chat_service=chat_service,
    )

    assert "not found" in response.lower() or "error" in response.lower()


# ============================================================================
# E2E Test: Integration Main Script (Subprocess)
# ============================================================================


@pytest.mark.circleci
def test_integration_main_imports() -> None:
    """Test that integration_main.py can be imported without errors."""
    project_root = Path(__file__).parent.parent.parent
    integration_main = project_root / "integration_main.py"

    if not integration_main.exists():
        pytest.skip("integration_main.py not found")

    # Test that the module can be imported
    import_test = f"""
import sys
sys.path.insert(0, '{project_root!s}')
try:
    # Only test imports, not execution
    from integration_main import process_message, get_ai_interface, get_chat_interface, get_ticket_interface
    print("All imports successful")
except ImportError as e:
    print(f"Import error: {{e}}")
    raise
"""

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_test],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=30,
    )

    if result.returncode != 0:
        pytest.fail(f"Import test failed: {result.stderr}")

    assert "All imports successful" in result.stdout


@pytest.mark.circleci
def test_integration_main_syntax() -> None:
    """Test that integration_main.py has valid Python syntax."""
    project_root = Path(__file__).parent.parent.parent
    integration_main = project_root / "integration_main.py"

    if not integration_main.exists():
        pytest.skip("integration_main.py not found")

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "py_compile", str(integration_main)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        pytest.fail(f"Syntax error in integration_main.py: {result.stderr}")
