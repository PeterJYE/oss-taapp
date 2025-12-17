"""Tests for StandardizedTicketAdapter to improve coverage."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from ticket_api.ticket_impl.models import Ticket as InternalTicket
from ticket_api.ticket_impl.models import TicketPriority, TicketStatus as InternalTicketStatus
from ticket_api.ticket_interface.shared_interface import TicketStatus as SharedTicketStatus

from ticket_api.ticket_adapter.adapter import StandardizedTicketAdapter
from ticket_api.ticket_impl.interface import TicketServiceAPI


class MockTicketServiceAPI(TicketServiceAPI):
    """Mock TicketServiceAPI for testing."""

    def __init__(self) -> None:
        """Initialize mock service."""
        self._tickets: dict[UUID, InternalTicket] = {}

    async def create_ticket(
        self,
        title: str,
        description: str,
        reporter: str,
        assignee: str | None = None,
    ) -> InternalTicket:
        """Create a mock ticket."""
        ticket_id = uuid4()
        ticket = InternalTicket(
            id=ticket_id,
            title=title,
            description=description,
            status=InternalTicketStatus.OPEN,
            assignee=assignee,
            reporter=reporter,
            priority=TicketPriority.MEDIUM,
        )
        self._tickets[ticket_id] = ticket
        return ticket

    async def get_ticket(self, ticket_id: UUID) -> InternalTicket | None:
        """Get a mock ticket."""
        return self._tickets.get(ticket_id)

    async def list_tickets(
        self,
        status: InternalTicketStatus | None = None,
    ) -> list[InternalTicket]:
        """List mock tickets."""
        tickets = list(self._tickets.values())
        if status:
            tickets = [t for t in tickets if t.status == status]
        return tickets

    async def update_ticket(
        self,
        ticket_id: UUID,
        status: InternalTicketStatus | None = None,
        title: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
    ) -> InternalTicket | None:
        """Update a mock ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        # Create updated ticket (immutable)
        updated = InternalTicket(
            id=ticket.id,
            title=title if title is not None else ticket.title,
            description=description if description is not None else ticket.description,
            status=status if status is not None else ticket.status,
            assignee=assignee if assignee is not None else ticket.assignee,
            reporter=ticket.reporter,
            priority=ticket.priority,
        )
        self._tickets[ticket_id] = updated
        return updated

    async def delete_ticket(self, ticket_id: UUID) -> bool:
        """Delete a mock ticket."""
        if ticket_id in self._tickets:
            del self._tickets[ticket_id]
            return True
        return False

    async def add_comment(self, ticket_id: UUID, content: str, author: str | None = None) -> None:
        """Add a comment to a mock ticket."""
        pass  # Not needed for adapter tests

    async def get_ticket_comments(self, ticket_id: UUID) -> list:
        """Get comments for a mock ticket."""
        return []  # Not needed for adapter tests

    async def reassign_ticket(self, ticket_id: UUID, assignee: str) -> InternalTicket | None:
        """Reassign a mock ticket."""
        return await self.update_ticket(ticket_id, assignee=assignee)

    async def transition_status(self, ticket_id: UUID, status: InternalTicketStatus) -> InternalTicket | None:
        """Transition a mock ticket status."""
        return await self.update_ticket(ticket_id, status=status)

    async def update_description(self, ticket_id: UUID, description: str) -> InternalTicket | None:
        """Update a mock ticket description."""
        return await self.update_ticket(ticket_id, description=description)

    async def update_priority(self, ticket_id: UUID, priority: TicketPriority) -> InternalTicket | None:
        """Update a mock ticket priority."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        # Create updated ticket with new priority
        updated = InternalTicket(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            assignee=ticket.assignee,
            reporter=ticket.reporter,
            priority=priority,
        )
        self._tickets[ticket_id] = updated
        return updated


@pytest.fixture
def mock_service() -> MockTicketServiceAPI:
    """Create a mock ticket service."""
    return MockTicketServiceAPI()


@pytest.fixture
def adapter(mock_service: MockTicketServiceAPI) -> StandardizedTicketAdapter:
    """Create an adapter with mock service."""
    return StandardizedTicketAdapter(mock_service, reporter="test-reporter")


def test_create_ticket(adapter: StandardizedTicketAdapter) -> None:
    """Test creating a ticket through the adapter."""
    ticket = adapter.create_ticket(
        title="Test Ticket",
        description="Test Description",
        assignee="test-assignee",
    )
    assert ticket.title == "Test Ticket"
    assert ticket.description == "Test Description"
    assert ticket.assignee == "test-assignee"
    assert ticket.status == SharedTicketStatus.OPEN


def test_create_ticket_no_assignee(adapter: StandardizedTicketAdapter) -> None:
    """Test creating a ticket without assignee."""
    ticket = adapter.create_ticket(
        title="Test Ticket",
        description="Test Description",
    )
    assert ticket.title == "Test Ticket"
    assert ticket.assignee is None


def test_get_ticket_found(adapter: StandardizedTicketAdapter) -> None:
    """Test getting an existing ticket."""
    # Create a ticket first
    created = adapter.create_ticket(
        title="Test Ticket",
        description="Test Description",
    )
    # Get it back
    retrieved = adapter.get_ticket(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.title == "Test Ticket"


def test_get_ticket_not_found(adapter: StandardizedTicketAdapter) -> None:
    """Test getting a non-existent ticket."""
    result = adapter.get_ticket(str(uuid4()))
    assert result is None


def test_get_ticket_invalid_uuid(adapter: StandardizedTicketAdapter) -> None:
    """Test getting a ticket with invalid UUID."""
    with pytest.raises(ValueError, match="Invalid ticket ID format"):
        adapter.get_ticket("not-a-uuid")


def test_search_tickets_by_status(adapter: StandardizedTicketAdapter) -> None:
    """Test searching tickets by status."""
    # Create tickets
    adapter.create_ticket(title="Open 1", description="Desc 1")
    adapter.create_ticket(title="Open 2", description="Desc 2")
    
    # Search for open tickets
    tickets = adapter.search_tickets(status=SharedTicketStatus.OPEN)
    assert len(tickets) == 2
    assert all(t.status == SharedTicketStatus.OPEN for t in tickets)


def test_search_tickets_by_query(adapter: StandardizedTicketAdapter) -> None:
    """Test searching tickets by query string."""
    adapter.create_ticket(title="Bug Fix", description="Fix the login bug")
    adapter.create_ticket(title="Feature", description="Add new feature")
    
    # Search by query
    tickets = adapter.search_tickets(query="bug")
    assert len(tickets) == 1
    assert "bug" in tickets[0].title.lower() or "bug" in tickets[0].description.lower()


def test_search_tickets_by_query_and_status(adapter: StandardizedTicketAdapter) -> None:
    """Test searching tickets by both query and status."""
    adapter.create_ticket(title="Bug Fix", description="Fix the login bug")
    adapter.create_ticket(title="Feature", description="Add new feature")
    
    tickets = adapter.search_tickets(query="bug", status=SharedTicketStatus.OPEN)
    assert len(tickets) == 1


def test_search_tickets_no_results(adapter: StandardizedTicketAdapter) -> None:
    """Test searching with no matching tickets."""
    tickets = adapter.search_tickets(query="nonexistent")
    assert len(tickets) == 0


def test_update_ticket_status(adapter: StandardizedTicketAdapter) -> None:
    """Test updating ticket status."""
    created = adapter.create_ticket(title="Test", description="Test")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        status=SharedTicketStatus.IN_PROGRESS,
    )
    assert updated is not None
    assert updated.status == SharedTicketStatus.IN_PROGRESS
    assert updated.id == created.id


def test_update_ticket_title(adapter: StandardizedTicketAdapter) -> None:
    """Test updating ticket title."""
    created = adapter.create_ticket(title="Old Title", description="Test")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        title="New Title",
    )
    assert updated is not None
    assert updated.title == "New Title"
    assert updated.description == "Test"


def test_update_ticket_description(adapter: StandardizedTicketAdapter) -> None:
    """Test updating ticket description."""
    created = adapter.create_ticket(title="Test", description="Old Desc")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        description="New Desc",
    )
    assert updated is not None
    assert updated.description == "New Desc"


def test_update_ticket_assignee(adapter: StandardizedTicketAdapter) -> None:
    """Test updating ticket assignee."""
    created = adapter.create_ticket(title="Test", description="Test")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        assignee="new-assignee",
    )
    assert updated is not None
    assert updated.assignee == "new-assignee"


def test_update_ticket_multiple_fields(adapter: StandardizedTicketAdapter) -> None:
    """Test updating multiple ticket fields."""
    created = adapter.create_ticket(title="Old", description="Old", assignee="old-assignee")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        status=SharedTicketStatus.CLOSED,
        title="New",
        description="New",
        assignee="new-assignee",
    )
    assert updated is not None
    assert updated.status == SharedTicketStatus.CLOSED
    assert updated.title == "New"
    assert updated.description == "New"
    assert updated.assignee == "new-assignee"


def test_update_ticket_not_found(adapter: StandardizedTicketAdapter) -> None:
    """Test updating a non-existent ticket."""
    with pytest.raises(ValueError, match="Ticket not found"):
        adapter.update_ticket(
            ticket_id=str(uuid4()),
            status=SharedTicketStatus.OPEN,
        )


def test_update_ticket_invalid_uuid(adapter: StandardizedTicketAdapter) -> None:
    """Test updating with invalid UUID."""
    with pytest.raises(ValueError, match="Invalid ticket ID format"):
        adapter.update_ticket(
            ticket_id="not-a-uuid",
            status=SharedTicketStatus.OPEN,
        )


def test_delete_ticket_success(adapter: StandardizedTicketAdapter) -> None:
    """Test deleting an existing ticket."""
    created = adapter.create_ticket(title="Test", description="Test")
    result = adapter.delete_ticket(created.id)
    assert result is True
    # Verify it's gone
    retrieved = adapter.get_ticket(created.id)
    assert retrieved is None


def test_delete_ticket_not_found(adapter: StandardizedTicketAdapter) -> None:
    """Test deleting a non-existent ticket."""
    result = adapter.delete_ticket(str(uuid4()))
    assert result is False


def test_delete_ticket_invalid_uuid(adapter: StandardizedTicketAdapter) -> None:
    """Test deleting with invalid UUID."""
    with pytest.raises(ValueError, match="Invalid ticket ID format"):
        adapter.delete_ticket("not-a-uuid")


def test_to_simple_conversion(adapter: StandardizedTicketAdapter) -> None:
    """Test conversion from internal to simple ticket."""
    created = adapter.create_ticket(title="Test", description="Test")
    # Verify the ticket has the correct shared interface fields
    assert hasattr(created, "id")
    assert hasattr(created, "title")
    assert hasattr(created, "description")
    assert hasattr(created, "status")
    assert hasattr(created, "assignee")


def test_status_mapping_open(adapter: StandardizedTicketAdapter) -> None:
    """Test status mapping for OPEN."""
    created = adapter.create_ticket(title="Test", description="Test")
    assert created.status == SharedTicketStatus.OPEN


def test_status_mapping_in_progress(adapter: StandardizedTicketAdapter) -> None:
    """Test status mapping for IN_PROGRESS."""
    created = adapter.create_ticket(title="Test", description="Test")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        status=SharedTicketStatus.IN_PROGRESS,
    )
    assert updated is not None
    assert updated.status == SharedTicketStatus.IN_PROGRESS


def test_status_mapping_closed(adapter: StandardizedTicketAdapter) -> None:
    """Test status mapping for CLOSED."""
    created = adapter.create_ticket(title="Test", description="Test")
    updated = adapter.update_ticket(
        ticket_id=created.id,
        status=SharedTicketStatus.CLOSED,
    )
    assert updated is not None
    assert updated.status == SharedTicketStatus.CLOSED


def test_adapter_with_custom_reporter() -> None:
    """Test adapter with custom reporter."""
    mock_service = MockTicketServiceAPI()
    adapter = StandardizedTicketAdapter(mock_service, reporter="custom-reporter")
    ticket = adapter.create_ticket(title="Test", description="Test")
    assert ticket.title == "Test"


def test_search_tickets_empty_query(adapter: StandardizedTicketAdapter) -> None:
    """Test searching with empty query."""
    adapter.create_ticket(title="Test", description="Test")
    tickets = adapter.search_tickets(query="")
    # Empty query should return all tickets
    assert len(tickets) >= 1


def test_search_tickets_none_query(adapter: StandardizedTicketAdapter) -> None:
    """Test searching with None query."""
    adapter.create_ticket(title="Test", description="Test")
    tickets = adapter.search_tickets(query=None)
    # None query should return all tickets
    assert len(tickets) >= 1


def test_to_simple_status_mapping_resolved(adapter: StandardizedTicketAdapter) -> None:
    """Test _to_simple maps RESOLVED status to CLOSED (line 124)."""
    from ticket_api.ticket_impl.models import Ticket as InternalTicket, TicketStatus as InternalTicketStatus
    from uuid import uuid4
    # Create an internal ticket with RESOLVED status
    internal_ticket = InternalTicket(
        id=uuid4(),
        title="Resolved Ticket",
        description="This is resolved",
        status=InternalTicketStatus.RESOLVED,
        assignee=None,
        reporter="test@example.com",
    )
    simple = adapter._to_simple(internal_ticket)
    assert simple.status == SharedTicketStatus.CLOSED


def test_to_simple_status_mapping_closed(adapter: StandardizedTicketAdapter) -> None:
    """Test _to_simple maps CLOSED status correctly (line 125)."""
    from ticket_api.ticket_impl.models import Ticket as InternalTicket, TicketStatus as InternalTicketStatus
    from uuid import uuid4
    # Create an internal ticket with CLOSED status
    internal_ticket = InternalTicket(
        id=uuid4(),
        title="Closed Ticket",
        description="This is closed",
        status=InternalTicketStatus.CLOSED,
        assignee=None,
        reporter="test@example.com",
    )
    simple = adapter._to_simple(internal_ticket)
    assert simple.status == SharedTicketStatus.CLOSED


def test_to_internal_status_mapping_closed(adapter: StandardizedTicketAdapter) -> None:
    """Test _to_internal_status maps CLOSED correctly (line 152)."""
    internal_status = adapter._to_internal_status(SharedTicketStatus.CLOSED)
    from ticket_api.ticket_impl.models import TicketStatus as InternalTicketStatus
    assert internal_status == InternalTicketStatus.CLOSED


def test_to_internal_status_mapping_open(adapter: StandardizedTicketAdapter) -> None:
    """Test _to_internal_status maps OPEN correctly."""
    internal_status = adapter._to_internal_status(SharedTicketStatus.OPEN)
    from ticket_api.ticket_impl.models import TicketStatus as InternalTicketStatus
    assert internal_status == InternalTicketStatus.OPEN


def test_to_internal_status_mapping_in_progress(adapter: StandardizedTicketAdapter) -> None:
    """Test _to_internal_status maps IN_PROGRESS correctly."""
    internal_status = adapter._to_internal_status(SharedTicketStatus.IN_PROGRESS)
    from ticket_api.ticket_impl.models import TicketStatus as InternalTicketStatus
    assert internal_status == InternalTicketStatus.IN_PROGRESS

