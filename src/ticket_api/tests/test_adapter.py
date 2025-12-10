"""Unit tests for the StandardizedTicketAdapter.

This test suite verifies that the adapter correctly translates between
the standardized TicketInterface and our internal TicketServiceAPI,
ensuring compliance with the shared interface requirements.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from ticket_api.ticket_adapter.adapter import SimpleTicket, StandardizedTicketAdapter
from ticket_api.ticket_impl.models import Ticket as InternalTicket
from ticket_api.ticket_impl.models import TicketPriority
from ticket_api.ticket_impl.models import TicketStatus as InternalTicketStatus
from ticket_api.ticket_interface.shared_interface import TicketStatus as SharedTicketStatus


class TestSimpleTicket:
    """Test the SimpleTicket wrapper class."""

    def test_simple_ticket_properties(self) -> None:
        """Test that SimpleTicket exposes the correct properties."""
        ticket = SimpleTicket(
            _id="123e4567-e89b-12d3-a456-426614174000",
            _title="Test Ticket",
            _description="Test Description",
            _status=SharedTicketStatus.OPEN,
            _assignee="user@example.com",
        )

        assert ticket.id == "123e4567-e89b-12d3-a456-426614174000"
        assert ticket.title == "Test Ticket"
        assert ticket.description == "Test Description"
        assert ticket.status == SharedTicketStatus.OPEN
        assert ticket.assignee == "user@example.com"

    def test_simple_ticket_no_assignee(self) -> None:
        """Test SimpleTicket with no assignee."""
        ticket = SimpleTicket(
            _id="123e4567-e89b-12d3-a456-426614174000",
            _title="Unassigned Ticket",
            _description="This ticket has no assignee",
            _status=SharedTicketStatus.IN_PROGRESS,
            _assignee=None,
        )

        assert ticket.assignee is None

    def test_simple_ticket_immutable(self) -> None:
        """Test that SimpleTicket is immutable (frozen dataclass)."""
        ticket = SimpleTicket(
            _id="123e4567-e89b-12d3-a456-426614174000",
            _title="Test",
            _description="Test",
            _status=SharedTicketStatus.OPEN,
            _assignee=None,
        )

        with pytest.raises((AttributeError, Exception), match=r"can't set attribute|cannot set|cannot assign"):
            ticket._title = "Modified"  # type: ignore[misc]


class TestStandardizedTicketAdapter:
    """Test the StandardizedTicketAdapter class."""

    @pytest.fixture
    def mock_internal_service(self) -> Any:
        """Create a mock internal TicketServiceAPI."""
        mock = MagicMock()
        # Configure all async methods as AsyncMocks upfront
        mock.create_ticket = AsyncMock()
        mock.get_ticket = AsyncMock()
        mock.list_tickets = AsyncMock()
        mock.update_ticket = AsyncMock()
        mock.delete_ticket = AsyncMock()
        mock.add_comment = AsyncMock()
        mock.get_ticket_comments = AsyncMock()
        mock.transition_status = AsyncMock()
        mock.reassign_ticket = AsyncMock()
        mock.update_priority = AsyncMock()
        mock.update_description = AsyncMock()
        return mock

    @pytest.fixture
    def adapter(self, mock_internal_service: Any) -> StandardizedTicketAdapter:
        """Create a StandardizedTicketAdapter with mocked internal service."""
        return StandardizedTicketAdapter(
            mock_internal_service,
            reporter="test-reporter",
        )

    @pytest.fixture
    def sample_internal_ticket(self) -> InternalTicket:
        """Create a sample internal ticket for testing."""
        ticket_id = uuid.uuid4()
        return InternalTicket(
            id=ticket_id,
            title="Sample Ticket",
            description="Sample Description",
            status=InternalTicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            assignee="user@example.com",
            reporter="reporter@example.com",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            comments=[],
        )

    def test_adapter_initialization(self, mock_internal_service: Any) -> None:
        """Test adapter initialization with custom reporter."""
        adapter = StandardizedTicketAdapter(
            mock_internal_service,
            reporter="custom-reporter",
        )
        assert adapter._internal == mock_internal_service
        assert adapter._reporter == "custom-reporter"

    def test_adapter_default_reporter(self, mock_internal_service: Any) -> None:
        """Test adapter uses 'system' as default reporter."""
        adapter = StandardizedTicketAdapter(mock_internal_service)
        assert adapter._reporter == "system"

    def test_to_simple_conversion(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test conversion from internal ticket to SimpleTicket."""
        simple = adapter._to_simple(sample_internal_ticket)

        assert simple.id == str(sample_internal_ticket.id)
        assert simple.title == sample_internal_ticket.title
        assert simple.description == sample_internal_ticket.description
        assert simple.status == SharedTicketStatus.OPEN
        assert simple.assignee == sample_internal_ticket.assignee

    def test_status_mapping_open(self, adapter: StandardizedTicketAdapter) -> None:
        """Test status mapping: OPEN -> OPEN."""
        internal_ticket = InternalTicket(
            title="Test",
            description="Test",
            status=InternalTicketStatus.OPEN,
            reporter="test",
        )
        simple = adapter._to_simple(internal_ticket)
        assert simple.status == SharedTicketStatus.OPEN

    def test_status_mapping_in_progress(self, adapter: StandardizedTicketAdapter) -> None:
        """Test status mapping: IN_PROGRESS -> IN_PROGRESS."""
        internal_ticket = InternalTicket(
            title="Test",
            description="Test",
            status=InternalTicketStatus.IN_PROGRESS,
            reporter="test",
        )
        simple = adapter._to_simple(internal_ticket)
        assert simple.status == SharedTicketStatus.IN_PROGRESS

    def test_status_mapping_resolved(self, adapter: StandardizedTicketAdapter) -> None:
        """Test status mapping: RESOLVED -> CLOSED."""
        internal_ticket = InternalTicket(
            title="Test",
            description="Test",
            status=InternalTicketStatus.RESOLVED,
            reporter="test",
        )
        simple = adapter._to_simple(internal_ticket)
        assert simple.status == SharedTicketStatus.CLOSED

    def test_status_mapping_closed(self, adapter: StandardizedTicketAdapter) -> None:
        """Test status mapping: CLOSED -> CLOSED."""
        internal_ticket = InternalTicket(
            title="Test",
            description="Test",
            status=InternalTicketStatus.CLOSED,
            reporter="test",
        )
        simple = adapter._to_simple(internal_ticket)
        assert simple.status == SharedTicketStatus.CLOSED

    def test_to_internal_status_open(self, adapter: StandardizedTicketAdapter) -> None:
        """Test reverse status mapping: OPEN -> OPEN."""
        internal = adapter._to_internal_status(SharedTicketStatus.OPEN)
        assert internal == InternalTicketStatus.OPEN

    def test_to_internal_status_in_progress(self, adapter: StandardizedTicketAdapter) -> None:
        """Test reverse status mapping: IN_PROGRESS -> IN_PROGRESS."""
        internal = adapter._to_internal_status(SharedTicketStatus.IN_PROGRESS)
        assert internal == InternalTicketStatus.IN_PROGRESS

    def test_to_internal_status_closed(self, adapter: StandardizedTicketAdapter) -> None:
        """Test reverse status mapping: CLOSED -> CLOSED."""
        internal = adapter._to_internal_status(SharedTicketStatus.CLOSED)
        assert internal == InternalTicketStatus.CLOSED

    def test_create_ticket(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test create_ticket delegates to internal service correctly."""
        adapter._internal.create_ticket.return_value = sample_internal_ticket  # type: ignore[attr-defined]

        result = adapter.create_ticket(
            title="New Ticket",
            description="New Description",
            assignee="assignee@example.com",
        )

        # Verify internal service was called with correct parameters
        adapter._internal.create_ticket.assert_called_once_with(  # type: ignore[attr-defined]
            title="New Ticket",
            description="New Description",
            reporter="test-reporter",
            assignee="assignee@example.com",
        )  # type: ignore[attr-defined]

        # Verify result is a SimpleTicket
        assert isinstance(result, SimpleTicket)
        assert result.title == sample_internal_ticket.title
        assert result.description == sample_internal_ticket.description

    def test_create_ticket_no_assignee(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test create_ticket without assignee."""
        adapter._internal.create_ticket.return_value = sample_internal_ticket  # type: ignore[attr-defined]

        result = adapter.create_ticket(
            title="Unassigned Ticket",
            description="No assignee",
        )

        adapter._internal.create_ticket.assert_called_once_with(  # type: ignore[attr-defined]
            title="Unassigned Ticket",
            description="No assignee",
            reporter="test-reporter",
            assignee=None,
        )  # type: ignore[attr-defined]

        assert isinstance(result, SimpleTicket)

    def test_get_ticket_found(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test get_ticket returns ticket when found."""
        adapter._internal.get_ticket.return_value = sample_internal_ticket  # type: ignore[attr-defined]
        ticket_id = str(sample_internal_ticket.id)

        result = adapter.get_ticket(ticket_id)

        adapter._internal.get_ticket.assert_called_once_with(sample_internal_ticket.id)  # type: ignore[attr-defined]
        assert isinstance(result, SimpleTicket)
        assert result.id == ticket_id

    def test_get_ticket_not_found(self, adapter: StandardizedTicketAdapter) -> None:
        """Test get_ticket returns None when ticket not found."""
        adapter._internal.get_ticket.return_value = None  # type: ignore[attr-defined]
        ticket_id = str(uuid.uuid4())

        result = adapter.get_ticket(ticket_id)

        assert result is None

    def test_get_ticket_invalid_uuid(self, adapter: StandardizedTicketAdapter) -> None:
        """Test get_ticket raises ValueError for invalid UUID."""
        with pytest.raises(ValueError, match="Invalid ticket ID format"):
            adapter.get_ticket("not-a-uuid")

    def test_search_tickets_no_filters(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test search_tickets without filters returns all tickets."""
        internal_tickets = [sample_internal_ticket]
        adapter._internal.list_tickets.return_value = internal_tickets  # type: ignore[attr-defined]

        result = adapter.search_tickets()

        adapter._internal.list_tickets.assert_called_once_with(status=None)  # type: ignore[attr-defined]
        assert len(result) == 1
        assert isinstance(result[0], SimpleTicket)

    def test_search_tickets_with_status(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test search_tickets with status filter."""
        internal_tickets = [sample_internal_ticket]
        adapter._internal.list_tickets.return_value = internal_tickets  # type: ignore[attr-defined]

        result = adapter.search_tickets(status=SharedTicketStatus.OPEN)

        adapter._internal.list_tickets.assert_called_once_with(  # type: ignore[attr-defined]
            status=InternalTicketStatus.OPEN,
        )  # type: ignore[attr-defined]
        assert len(result) == 1

    def test_search_tickets_with_query(self, adapter: StandardizedTicketAdapter) -> None:
        """Test search_tickets with text query filters results."""
        ticket1 = InternalTicket(
            title="Bug in login",
            description="Users cannot log in",
            reporter="user1",
            status=InternalTicketStatus.OPEN,
        )
        ticket2 = InternalTicket(
            title="Feature request",
            description="Add dark mode",
            reporter="user2",
            status=InternalTicketStatus.OPEN,
        )
        ticket3 = InternalTicket(
            title="Login page redesign",
            description="Improve UI",
            reporter="user3",
            status=InternalTicketStatus.OPEN,
        )

        adapter._internal.list_tickets.return_value = [ticket1, ticket2, ticket3]  # type: ignore[attr-defined]

        result = adapter.search_tickets(query="login")

        # Should match ticket1 (title contains "login") and ticket3 (title contains "Login")
        expected_matches = 2
        assert len(result) == expected_matches
        titles = {t.title for t in result}
        assert "Bug in login" in titles
        assert "Login page redesign" in titles

    def test_search_tickets_query_case_insensitive(
        self,
        adapter: StandardizedTicketAdapter,
    ) -> None:
        """Test search_tickets query is case-insensitive."""
        ticket = InternalTicket(
            title="URGENT Bug",
            description="Critical issue",
            reporter="user1",
            status=InternalTicketStatus.OPEN,
        )
        adapter._internal.list_tickets.return_value = [ticket]  # type: ignore[attr-defined]

        result = adapter.search_tickets(query="urgent")

        assert len(result) == 1
        assert result[0].title == "URGENT Bug"

    def test_search_tickets_query_searches_description(
        self,
        adapter: StandardizedTicketAdapter,
    ) -> None:
        """Test search_tickets query also searches description."""
        ticket = InternalTicket(
            title="Random Title",
            description="This mentions authentication",
            reporter="user1",
            status=InternalTicketStatus.OPEN,
        )
        adapter._internal.list_tickets.return_value = [ticket]  # type: ignore[attr-defined]

        result = adapter.search_tickets(query="authentication")

        assert len(result) == 1

    def test_search_tickets_with_status_and_query(self, adapter: StandardizedTicketAdapter) -> None:
        """Test search_tickets with both status and query filters."""
        ticket1 = InternalTicket(
            title="Bug in login",
            description="Test",
            reporter="user1",
            status=InternalTicketStatus.OPEN,
        )

        adapter._internal.list_tickets.return_value = [ticket1]  # type: ignore[attr-defined]

        result = adapter.search_tickets(
            query="login",
            status=SharedTicketStatus.OPEN,
        )

        adapter._internal.list_tickets.assert_called_once_with(  # type: ignore[attr-defined]
            status=InternalTicketStatus.OPEN,
        )  # type: ignore[attr-defined]
        assert len(result) == 1

    def test_update_ticket_status(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test update_ticket with status update."""
        updated_ticket = InternalTicket(
            id=sample_internal_ticket.id,
            title=sample_internal_ticket.title,
            description=sample_internal_ticket.description,
            status=InternalTicketStatus.IN_PROGRESS,
            reporter="test",
        )
        adapter._internal.update_ticket.return_value = updated_ticket  # type: ignore[attr-defined]
        ticket_id = str(sample_internal_ticket.id)

        result = adapter.update_ticket(
            ticket_id,
            status=SharedTicketStatus.IN_PROGRESS,
        )

        adapter._internal.update_ticket.assert_called_once_with(  # type: ignore[attr-defined]
            ticket_id=sample_internal_ticket.id,
            status=InternalTicketStatus.IN_PROGRESS,
            title=None,
            description=None,
            assignee=None,
        )  # type: ignore[attr-defined]
        assert isinstance(result, SimpleTicket)
        assert result.status == SharedTicketStatus.IN_PROGRESS

    def test_update_ticket_title(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test update_ticket with title update."""
        updated_ticket = InternalTicket(
            id=sample_internal_ticket.id,
            title="Updated Title",
            description=sample_internal_ticket.description,
            status=sample_internal_ticket.status,
            reporter="test",
        )
        adapter._internal.update_ticket.return_value = updated_ticket  # type: ignore[attr-defined]
        ticket_id = str(sample_internal_ticket.id)

        result = adapter.update_ticket(ticket_id, title="Updated Title")

        adapter._internal.update_ticket.assert_called_once_with(  # type: ignore[attr-defined]
            ticket_id=sample_internal_ticket.id,
            status=None,
            title="Updated Title",
            description=None,
            assignee=None,
        )  # type: ignore[attr-defined]
        assert result.title == "Updated Title"

    def test_update_ticket_both_fields(
        self,
        adapter: StandardizedTicketAdapter,
        sample_internal_ticket: InternalTicket,
    ) -> None:
        """Test update_ticket with both status and title."""
        updated_ticket = InternalTicket(
            id=sample_internal_ticket.id,
            title="New Title",
            description=sample_internal_ticket.description,
            status=InternalTicketStatus.CLOSED,
            reporter="test",
        )
        adapter._internal.update_ticket.return_value = updated_ticket  # type: ignore[attr-defined]
        ticket_id = str(sample_internal_ticket.id)

        result = adapter.update_ticket(
            ticket_id,
            status=SharedTicketStatus.CLOSED,
            title="New Title",
        )

        adapter._internal.update_ticket.assert_called_once_with(  # type: ignore[attr-defined]
            ticket_id=sample_internal_ticket.id,
            status=InternalTicketStatus.CLOSED,
            title="New Title",
            description=None,
            assignee=None,
        )  # type: ignore[attr-defined]
        assert result.status == SharedTicketStatus.CLOSED
        assert result.title == "New Title"

    def test_update_ticket_not_found(self, adapter: StandardizedTicketAdapter) -> None:
        """Test update_ticket raises ValueError when ticket not found."""
        adapter._internal.update_ticket.return_value = None  # type: ignore[attr-defined]
        ticket_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="Ticket not found"):
            adapter.update_ticket(ticket_id, title="New Title")

    def test_update_ticket_invalid_uuid(self, adapter: StandardizedTicketAdapter) -> None:
        """Test update_ticket raises ValueError for invalid UUID."""
        with pytest.raises(ValueError, match="Invalid ticket ID format"):
            adapter.update_ticket("not-a-uuid", title="New Title")

    def test_delete_ticket_success(self, adapter: StandardizedTicketAdapter) -> None:
        """Test delete_ticket returns True when successful."""
        ticket_id = str(uuid.uuid4())
        adapter._internal.delete_ticket.return_value = True  # type: ignore[attr-defined]

        result = adapter.delete_ticket(ticket_id)

        assert result is True

    def test_delete_ticket_not_found(self, adapter: StandardizedTicketAdapter) -> None:
        """Test delete_ticket returns False when ticket not found."""
        ticket_id = str(uuid.uuid4())
        adapter._internal.delete_ticket.return_value = False  # type: ignore[attr-defined]

        result = adapter.delete_ticket(ticket_id)

        assert result is False

    def test_delete_ticket_invalid_uuid(self, adapter: StandardizedTicketAdapter) -> None:
        """Test delete_ticket raises ValueError for invalid UUID."""
        with pytest.raises(ValueError, match="Invalid ticket ID format"):
            adapter.delete_ticket("not-a-uuid")


class TestAdapterIntegration:
    """Integration tests for the adapter with realistic scenarios."""

    @pytest.fixture
    def mock_internal_service(self) -> Any:
        """Create a realistic mock service."""
        mock = MagicMock()
        # Configure all async methods as AsyncMocks upfront
        mock.create_ticket = AsyncMock()
        mock.get_ticket = AsyncMock()
        mock.list_tickets = AsyncMock()
        mock.update_ticket = AsyncMock()
        mock.delete_ticket = AsyncMock()
        return mock

    @pytest.fixture
    def adapter(self, mock_internal_service: Any) -> StandardizedTicketAdapter:
        """Create an adapter instance."""
        return StandardizedTicketAdapter(mock_internal_service)

    def test_full_ticket_lifecycle(self, adapter: StandardizedTicketAdapter) -> None:
        """Test creating, updating, retrieving, and deleting a ticket."""
        ticket_id = uuid.uuid4()

        # Create ticket
        created_ticket = InternalTicket(
            id=ticket_id,
            title="Bug Report",
            description="App crashes on startup",
            status=InternalTicketStatus.OPEN,
            reporter="system",
            assignee="dev@example.com",
        )
        adapter._internal.create_ticket.return_value = created_ticket  # type: ignore[attr-defined]

        result = adapter.create_ticket(
            title="Bug Report",
            description="App crashes on startup",
            assignee="dev@example.com",
        )
        assert result.status == SharedTicketStatus.OPEN

        # Get ticket
        adapter._internal.get_ticket.return_value = created_ticket  # type: ignore[attr-defined]
        retrieved = adapter.get_ticket(str(ticket_id))
        assert retrieved is not None
        assert retrieved.title == "Bug Report"

        # Update ticket
        updated_ticket = InternalTicket(
            id=ticket_id,
            title="Bug Report",
            description="App crashes on startup",
            status=InternalTicketStatus.IN_PROGRESS,
            reporter="system",
            assignee="dev@example.com",
        )
        adapter._internal.update_ticket.return_value = updated_ticket  # type: ignore[attr-defined]

        updated = adapter.update_ticket(
            str(ticket_id),
            status=SharedTicketStatus.IN_PROGRESS,
        )
        assert updated.status == SharedTicketStatus.IN_PROGRESS

        # Delete ticket
        adapter._internal.delete_ticket.return_value = True  # type: ignore[attr-defined]
        deleted = adapter.delete_ticket(str(ticket_id))
        assert deleted is True
