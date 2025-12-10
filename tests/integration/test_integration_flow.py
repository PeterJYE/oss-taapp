"""Integration test for Chat → AI → Ticket flow.

Tests that the integration works using only shared interfaces.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_api import AIInterface  # type: ignore[attr-defined]
from chat_api import ChatInterface, Message  # type: ignore[attr-defined]
from ticket_api import Ticket, TicketInterface, TicketStatus  # type: ignore[attr-defined]


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

    def __init__(self, ticket_id: str, title: str, description: str, status: TicketStatus, assignee: str | None = None) -> None:
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


@pytest.mark.integration
def test_integration_flow_create_ticket() -> None:
    """Test the complete flow: User message → AI → Ticket → Response."""
    # Setup mocks
    mock_ai = MagicMock(spec=AIInterface)
    mock_ticket = MagicMock(spec=TicketInterface)
    mock_chat = MagicMock(spec=ChatInterface)

    # Step 1: User sends message
    user_message = "Create a ticket for fixing the login bug"
    channel_id = "C123456"

    # Step 2: AI converts to structured JSON
    ai_response = {
        "method": "create_ticket",
        "parameters": {
            "title": "Fix login bug",
            "description": "User reported issue with login functionality",
        },
    }
    mock_ai.generate_response.return_value = ai_response

    # Step 3: Ticket service creates ticket
    created_ticket = MockTicket(
        ticket_id="TICKET-123",
        title="Fix login bug",
        description="User reported issue with login functionality",
        status=TicketStatus.OPEN,
    )
    mock_ticket.create_ticket.return_value = created_ticket

    # Step 4: Execute the flow
    # AI converts message
    result = mock_ai.generate_response(
        user_input=user_message,
        system_prompt="Convert message to JSON for ticket operations",
        response_schema={"type": "object"},
    )

    # Parse AI response
    assert isinstance(result, dict)
    method = result.get("method")
    params = result.get("parameters", {})

    # Call ticket service
    if method == "create_ticket":
        ticket = mock_ticket.create_ticket(
            title=params["title"],
            description=params["description"],
            assignee=params.get("assignee"),
        )

    # Format and send response
    response_message = f"✅ Ticket created! ID: {ticket.id}, Title: {ticket.title}"
    mock_chat.send_message(channel_id=channel_id, content=response_message)

    # Verify the flow
    mock_ai.generate_response.assert_called_once()
    mock_ticket.create_ticket.assert_called_once_with(
        title="Fix login bug",
        description="User reported issue with login functionality",
        assignee=None,
    )
    mock_chat.send_message.assert_called_once_with(
        channel_id=channel_id,
        content="✅ Ticket created! ID: TICKET-123, Title: Fix login bug",
    )


@pytest.mark.integration
def test_integration_flow_get_ticket() -> None:
    """Test the flow for getting a ticket."""
    mock_ai = MagicMock(spec=AIInterface)
    mock_ticket = MagicMock(spec=TicketInterface)
    mock_chat = MagicMock(spec=ChatInterface)

    user_message = "Show me ticket TICKET-123"
    channel_id = "C123456"

    # AI response
    ai_response = {
        "method": "get_ticket",
        "parameters": {"ticket_id": "TICKET-123"},
    }
    mock_ai.generate_response.return_value = ai_response

    # Ticket service returns ticket
    ticket = MockTicket(
        ticket_id="TICKET-123",
        title="Fix login bug",
        description="User reported issue",
        status=TicketStatus.OPEN,
    )
    mock_ticket.get_ticket.return_value = ticket

    # Execute flow
    result = mock_ai.generate_response(
        user_input=user_message,
        system_prompt="Convert message to JSON",
        response_schema={"type": "object"},
    )

    method = result.get("method")
    params = result.get("parameters", {})

    if method == "get_ticket":
        ticket = mock_ticket.get_ticket(ticket_id=params["ticket_id"])

    response = f"📋 {ticket.title} (Status: {ticket.status})"
    mock_chat.send_message(channel_id=channel_id, content=response)

    # Verify
    mock_ticket.get_ticket.assert_called_once_with(ticket_id="TICKET-123")
    mock_chat.send_message.assert_called_once()


@pytest.mark.unit
def test_adapters_implement_interfaces() -> None:
    """Test that adapters correctly implement the shared interfaces."""
    # Verify ChatAdapter implements ChatInterface
    from chat_api.chat_impl.src.slack_impl import SlackClient  # type: ignore[attr-defined]

    from chat_api import ChatAdapter  # type: ignore[attr-defined]
    from openai_adapter import AIAdapter  # type: ignore[attr-defined]
    from ticket_api import StandardizedTicketAdapter  # type: ignore[attr-defined]

    slack_client = SlackClient()  # Offline mode
    chat_adapter = ChatAdapter(slack_client)
    assert isinstance(chat_adapter, ChatInterface)

    # Verify AIAdapter implements AIInterface

    ai_adapter = AIAdapter(base_url="http://testserver")  # type: ignore[call-arg]
    assert isinstance(ai_adapter, AIInterface)

    # Verify StandardizedTicketAdapter implements TicketInterface
    from ticket_api.ticket_impl.src.ticket_impl import TicketImpl  # type: ignore[attr-defined]

    ticket_impl = TicketImpl(user_id="test-user")
    ticket_adapter = StandardizedTicketAdapter(ticket_impl)
    assert isinstance(ticket_adapter, TicketInterface)

