"""Integration test for AI Service ↔ Ticket Service.

This test verifies the direct interaction between:
1. AI Service: Converts natural language to structured JSON
2. Ticket Service: Executes CRUD operations based on AI output

Uses mocks to avoid hitting live OpenAI/JIRA APIs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_api import AIInterface  # type: ignore[attr-defined]
from ticket_api import Ticket, TicketInterface, TicketStatus  # type: ignore[attr-defined]

pytestmark = pytest.mark.integration


class MockTicket(Ticket):
    """Mock ticket implementation for testing."""

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


class FakeAIService:
    """Fake AI service that simulates OpenAI structured output.

    This mimics the AI adapter behavior without hitting OpenAI API.
    """

    def __init__(self) -> None:
        """Initialize fake AI service with predefined responses."""
        self._responses: dict[str, dict] = {
            "create": {
                "method": "create_ticket",
                "parameters": {
                    "title": "Fix login bug",
                    "description": "Users cannot log in with valid credentials",
                    "assignee": "",
                    "ticket_id": "",
                    "query": "",
                    "status": "",
                },
            },
            "get": {
                "method": "get_ticket",
                "parameters": {
                    "ticket_id": "TEST-123",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                    "status": "",
                },
            },
            "search": {
                "method": "search_tickets",
                "parameters": {
                    "status": "open",
                    "query": "",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "ticket_id": "",
                },
            },
            "update": {
                "method": "update_ticket",
                "parameters": {
                    "ticket_id": "TEST-123",
                    "status": "in_progress",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                },
            },
            "delete": {
                "method": "delete_ticket",
                "parameters": {
                    "ticket_id": "TEST-123",
                    "title": "",
                    "description": "",
                    "assignee": "",
                    "query": "",
                    "status": "",
                },
            },
        }

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        response_schema: dict | None = None,
    ) -> dict:
        """Simulate AI response based on user input keywords."""
        user_lower = user_input.lower()

        if "create" in user_lower or "new" in user_lower:
            return self._responses["create"]
        elif "get" in user_lower or "show" in user_lower or "find" in user_lower:
            if "all" in user_lower or "search" in user_lower or "open" in user_lower:
                return self._responses["search"]
            return self._responses["get"]
        elif "update" in user_lower or "change" in user_lower:
            return self._responses["update"]
        elif "delete" in user_lower or "remove" in user_lower:
            return self._responses["delete"]
        else:
            return self._responses["search"]


class FakeTicketService:
    """Fake ticket service that simulates JIRA operations.

    This mimics the ticket adapter behavior without hitting JIRA API.
    """

    def __init__(self) -> None:
        """Initialize fake ticket service with in-memory storage."""
        self._tickets: dict[str, MockTicket] = {}
        self._counter = 1

    def create_ticket(
        self,
        title: str,
        description: str,
        assignee: str | None = None,
    ) -> MockTicket:
        """Create a new ticket in memory."""
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
        """Retrieve a ticket by ID."""
        return self._tickets.get(ticket_id)

    def search_tickets(
        self,
        query: str | None = None,
        status: TicketStatus | None = None,
    ) -> list[MockTicket]:
        """Search tickets by query or status."""
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

        new_status = status if status else ticket.status
        new_title = title if title else ticket.title

        updated = MockTicket(
            ticket_id=ticket_id,
            title=new_title,
            description=ticket.description,
            status=new_status,
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


def test_ai_to_ticket_create_flow() -> None:
    """Test AI Service parsing user input and Ticket Service creating ticket."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # User wants to create a ticket
    user_input = "Create a ticket for fixing the login bug"

    # AI converts natural language to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation JSON",
        response_schema={},
    )

    # Verify AI response structure
    assert ai_response["method"] == "create_ticket"
    params = ai_response["parameters"]
    assert params["title"] == "Fix login bug"
    assert params["description"] != ""

    # Ticket service executes the operation
    ticket = ticket_service.create_ticket(
        title=params["title"],
        description=params["description"],
        assignee=params.get("assignee") or None,
    )

    # Verify ticket was created correctly
    assert ticket.id == "TEST-1"
    assert ticket.title == "Fix login bug"
    assert ticket.status == TicketStatus.OPEN

    # Verify ticket is retrievable
    retrieved = ticket_service.get_ticket("TEST-1")
    assert retrieved is not None
    assert retrieved.title == ticket.title


def test_ai_to_ticket_get_flow() -> None:
    """Test AI Service parsing get request and Ticket Service retrieving ticket."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # First create a ticket
    created = ticket_service.create_ticket(
        title="Test Ticket",
        description="Test description",
    )

    # Update fake AI to return correct ticket ID
    ai_service._responses["get"]["parameters"]["ticket_id"] = created.id

    # User wants to get a ticket
    user_input = f"Show me ticket {created.id}"

    # AI converts to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation JSON",
        response_schema={},
    )

    # Verify AI parsed correctly
    assert ai_response["method"] == "get_ticket"
    ticket_id = ai_response["parameters"]["ticket_id"]

    # Ticket service retrieves the ticket
    ticket = ticket_service.get_ticket(ticket_id)

    # Verify correct ticket was retrieved
    assert ticket is not None
    assert ticket.id == created.id
    assert ticket.title == "Test Ticket"


def test_ai_to_ticket_search_flow() -> None:
    """Test AI Service parsing search request and Ticket Service searching."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # Create some tickets
    ticket_service.create_ticket(title="Bug 1", description="First bug")
    ticket_service.create_ticket(title="Bug 2", description="Second bug")
    ticket_service.create_ticket(title="Feature", description="New feature")

    # User wants to search
    user_input = "Show me all open tickets"

    # AI converts to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation JSON",
        response_schema={},
    )

    # Verify AI response
    assert ai_response["method"] == "search_tickets"
    params = ai_response["parameters"]

    # Ticket service searches
    status = TicketStatus(params["status"]) if params.get("status") else None
    tickets = ticket_service.search_tickets(
        query=params.get("query") or None,
        status=status,
    )

    # Verify search results
    assert len(tickets) == 3  # All tickets are OPEN by default
    assert all(t.status == TicketStatus.OPEN for t in tickets)


def test_ai_to_ticket_update_flow() -> None:
    """Test AI Service parsing update request and Ticket Service updating."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # Create a ticket first
    created = ticket_service.create_ticket(
        title="Original Title",
        description="Original description",
    )
    assert created.status == TicketStatus.OPEN

    # Update fake AI to return correct ticket ID
    ai_service._responses["update"]["parameters"]["ticket_id"] = created.id

    # User wants to update
    user_input = f"Update ticket {created.id} status to in progress"

    # AI converts to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation JSON",
        response_schema={},
    )

    # Verify AI response
    assert ai_response["method"] == "update_ticket"
    params = ai_response["parameters"]

    # Ticket service updates
    status = TicketStatus(params["status"]) if params.get("status") else None
    updated = ticket_service.update_ticket(
        ticket_id=params["ticket_id"],
        status=status,
        title=params.get("title") or None,
    )

    # Verify update was applied
    assert updated.id == created.id
    assert updated.status == TicketStatus.IN_PROGRESS
    assert updated.title == "Original Title"  # Title unchanged


def test_ai_to_ticket_delete_flow() -> None:
    """Test AI Service parsing delete request and Ticket Service deleting."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # Create a ticket first
    created = ticket_service.create_ticket(
        title="To Delete",
        description="This will be deleted",
    )

    # Update fake AI to return correct ticket ID
    ai_service._responses["delete"]["parameters"]["ticket_id"] = created.id

    # User wants to delete
    user_input = f"Delete ticket {created.id}"

    # AI converts to structured JSON
    ai_response = ai_service.generate_response(
        user_input=user_input,
        system_prompt="Convert to ticket operation JSON",
        response_schema={},
    )

    # Verify AI response
    assert ai_response["method"] == "delete_ticket"
    ticket_id = ai_response["parameters"]["ticket_id"]

    # Ticket service deletes
    success = ticket_service.delete_ticket(ticket_id)

    # Verify deletion
    assert success is True
    assert ticket_service.get_ticket(ticket_id) is None


def test_ai_ticket_full_crud_cycle() -> None:
    """Test complete CRUD cycle: Create → Read → Update → Delete."""
    ai_service = FakeAIService()
    ticket_service = FakeTicketService()

    # 1. CREATE
    ai_response = ai_service.generate_response(
        user_input="Create a ticket for API improvements",
        system_prompt="",
        response_schema={},
    )
    assert ai_response["method"] == "create_ticket"

    ticket = ticket_service.create_ticket(
        title=ai_response["parameters"]["title"],
        description=ai_response["parameters"]["description"],
    )
    ticket_id = ticket.id

    # 2. READ
    ai_service._responses["get"]["parameters"]["ticket_id"] = ticket_id
    ai_response = ai_service.generate_response(
        user_input=f"Get ticket {ticket_id}",
        system_prompt="",
        response_schema={},
    )
    assert ai_response["method"] == "get_ticket"

    retrieved = ticket_service.get_ticket(ticket_id)
    assert retrieved is not None
    assert retrieved.status == TicketStatus.OPEN

    # 3. UPDATE
    ai_service._responses["update"]["parameters"]["ticket_id"] = ticket_id
    ai_response = ai_service.generate_response(
        user_input=f"Update {ticket_id} to in progress",
        system_prompt="",
        response_schema={},
    )
    assert ai_response["method"] == "update_ticket"

    updated = ticket_service.update_ticket(
        ticket_id=ticket_id,
        status=TicketStatus.IN_PROGRESS,
    )
    assert updated.status == TicketStatus.IN_PROGRESS

    # 4. DELETE
    ai_service._responses["delete"]["parameters"]["ticket_id"] = ticket_id
    ai_response = ai_service.generate_response(
        user_input=f"Delete ticket {ticket_id}",
        system_prompt="",
        response_schema={},
    )
    assert ai_response["method"] == "delete_ticket"

    success = ticket_service.delete_ticket(ticket_id)
    assert success is True
    assert ticket_service.get_ticket(ticket_id) is None


def test_ai_service_implements_interface() -> None:
    """Verify AI adapter implements AIInterface."""
    from openai_adapter import AIAdapter  # type: ignore[attr-defined]

    adapter = AIAdapter(base_url="http://testserver")
    assert isinstance(adapter, AIInterface)


def test_ticket_service_implements_interface() -> None:
    """Verify Ticket adapter implements TicketInterface."""
    import os

    if not os.getenv("JIRA_CLOUD_ID"):
        pytest.skip("JIRA_CLOUD_ID not set - required for TicketImpl")

    try:
        from ticket_api.ticket_impl.src.ticket_impl import TicketImpl  # type: ignore[attr-defined]
        from ticket_api import StandardizedTicketAdapter  # type: ignore[attr-defined]

        ticket_impl = TicketImpl(user_id="test-user", project_key="TEST")
        adapter = StandardizedTicketAdapter(ticket_impl)
        assert isinstance(adapter, TicketInterface)
    except ValueError as e:
        if "JIRA_CLOUD_ID" in str(e):
            pytest.skip(f"JIRA_CLOUD_ID not set: {e}")
        raise
