"""Tests for the ticket API contract.

This module tests the data models and ensures the abstract interface
cannot be instantiated directly.
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from ticket_api.ticket_impl.exceptions import ServiceError, TicketNotFoundError
from ticket_api.ticket_impl.interface import TicketServiceAPI
from ticket_api.ticket_impl.models import Comment, Ticket, TicketPriority, TicketStatus


class TestTicketModel:
    """Test cases for the Ticket data model."""

    def test_ticket_creation_with_defaults(self) -> None:
        """Test creating a ticket with minimal required fields."""
        ticket = Ticket(
            title="Test ticket",
            description="This is a test ticket",
            reporter="test@example.com",
        )

        assert ticket.title == "Test ticket"
        assert ticket.description == "This is a test ticket"
        assert ticket.reporter == "test@example.com"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.assignee is None
        assert isinstance(ticket.id, UUID)
        assert isinstance(ticket.created_at, datetime)
        assert isinstance(ticket.updated_at, datetime)
        assert ticket.comments == []

    def test_ticket_creation_with_all_fields(self) -> None:
        """Test creating a ticket with all fields specified."""
        ticket_id = uuid4()
        created_time = datetime.now(UTC)

        ticket = Ticket(
            id=ticket_id,
            title="High priority bug",
            description="Critical system failure",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.CRITICAL,
            assignee="dev@example.com",
            reporter="user@example.com",
            created_at=created_time,
            updated_at=created_time,
        )

        assert ticket.id == ticket_id
        assert ticket.title == "High priority bug"
        assert ticket.description == "Critical system failure"
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.priority == TicketPriority.CRITICAL
        assert ticket.assignee == "dev@example.com"
        assert ticket.reporter == "user@example.com"
        assert ticket.created_at == created_time
        assert ticket.updated_at == created_time


class TestCommentModel:
    """Test cases for the Comment data model."""

    def test_comment_creation(self) -> None:
        """Test creating a comment with all required fields."""
        ticket_id = uuid4()
        comment = Comment(
            ticket_id=ticket_id,
            author="commenter@example.com",
            content="This is a test comment",
        )

        assert comment.ticket_id == ticket_id
        assert comment.author == "commenter@example.com"
        assert comment.content == "This is a test comment"
        assert isinstance(comment.id, UUID)
        assert isinstance(comment.created_at, datetime)

    def test_comment_immutability(self) -> None:
        """Test that comments are immutable once created - they cannot be modified after creation.

        Frozen dataclasses prevent modification after instantiation. This property is
        enforced at runtime, preventing tickets from modifying their own state.
        """
        from dataclasses import FrozenInstanceError

        comment = Comment(
            ticket_id=uuid4(),
            author="commenter@example.com",
            content="This is a test comment",
        )

        # Verify the comment cannot be modified - frozen dataclasses raise
        # FrozenInstanceError on attribute assignment. This assignment intentionally
        # violates the read-only property to test immutability at runtime.
        with pytest.raises(FrozenInstanceError):
            comment.content = "Modified content"  # type: ignore[misc]


class IncompleteImplementation(TicketServiceAPI):
    """Incomplete implementation missing some methods."""

    async def create_ticket(
        self,
        title: str,
        description: str,
        reporter: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: str | None = None,
    ) -> Ticket:
        """Create a ticket."""
        return Ticket(title=title, description=description, reporter=reporter)


class CompleteImplementation(TicketServiceAPI):
    """Complete implementation with all required methods."""

    async def create_ticket(
        self,
        title: str,
        description: str,
        reporter: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: str | None = None,
    ) -> Ticket:
        """Create a ticket."""
        return Ticket(
            title=title,
            description=description,
            reporter=reporter,
            priority=priority,
            assignee=assignee,
        )

    async def get_ticket(self, ticket_id: UUID) -> Ticket | None:
        """Get a ticket."""
        return None

    async def list_tickets(
        self,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets."""
        return []

    async def update_ticket(
        self,
        ticket_id: UUID,
        title: str | None = None,
        description: str | None = None,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        assignee: str | None = None,
    ) -> Ticket | None:
        """Update a ticket.

        Multiple parameters to support flexible partial updates.
        """
        return None

    async def delete_ticket(self, ticket_id: UUID) -> bool:
        """Delete a ticket."""
        return False

    async def add_comment(
        self,
        ticket_id: UUID,
        author: str,
        content: str,
    ) -> Comment | None:
        """Add a comment."""
        return None

    async def get_ticket_comments(self, ticket_id: UUID) -> list[Comment]:
        """Get ticket comments."""
        return []

    async def transition_status(
        self,
        ticket_id: UUID,
        new_status: TicketStatus,
    ) -> Ticket | None:
        """Transition status."""
        return None

    async def reassign_ticket(
        self,
        ticket_id: UUID,
        new_assignee: str,
    ) -> Ticket | None:
        """Reassign ticket."""
        return None

    async def update_priority(
        self,
        ticket_id: UUID,
        new_priority: TicketPriority,
    ) -> Ticket | None:
        """Update priority."""
        return None

    async def update_description(
        self,
        ticket_id: UUID,
        new_description: str,
    ) -> Ticket | None:
        """Update description."""
        return None


class TestTicketServiceAPI:
    """Test cases for the TicketServiceAPI abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that TicketServiceAPI cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # This test intentionally attempts to instantiate an abstract class.
            # Casting to Any bypasses mypy's abstract class check to allow testing
            # that the runtime correctly raises TypeError for incomplete implementations.
            cast("Any", TicketServiceAPI)()

    def test_concrete_implementation_must_implement_all_methods(self) -> None:
        """Test that concrete implementations must implement all abstract methods."""
        # Should not be able to instantiate incomplete implementation
        with pytest.raises(TypeError):
            # This test intentionally attempts to instantiate an incomplete implementation.
            # Casting to Any bypasses mypy's abstract class check to allow testing
            # that the runtime correctly raises TypeError for missing abstract methods.
            cast("Any", IncompleteImplementation)()

    def test_complete_implementation_can_be_instantiated(self) -> None:
        """Test that complete implementations can be instantiated."""
        # Should be able to instantiate complete implementation
        service = CompleteImplementation()
        assert isinstance(service, TicketServiceAPI)


class TestExceptions:
    """Test cases for custom exceptions."""

    def test_service_error_creation(self) -> None:
        """Test creating a ServiceError."""
        error = ServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_ticket_not_found_error_creation(self) -> None:
        """Test creating a TicketNotFoundError."""
        ticket_id = uuid4()
        error = TicketNotFoundError(ticket_id)
        assert error.ticket_id == ticket_id
        assert f"Ticket {ticket_id} not found" in str(error)
        assert isinstance(error, ServiceError)

    def test_ticket_not_found_error_is_exception(self) -> None:
        """Test that TicketNotFoundError is an Exception subclass."""
        ticket_id = uuid4()
        error = TicketNotFoundError(ticket_id)
        assert isinstance(error, Exception)


class TestEnums:
    """Test cases for the enum classes."""

    def test_ticket_status_values(self) -> None:
        """Test that TicketStatus has expected values."""
        assert TicketStatus.OPEN.value == "open"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.RESOLVED.value == "resolved"
        assert TicketStatus.CLOSED.value == "closed"

    def test_ticket_priority_values(self) -> None:
        """Test that TicketPriority has expected values."""
        assert TicketPriority.LOW.value == "low"
        assert TicketPriority.MEDIUM.value == "medium"
        assert TicketPriority.HIGH.value == "high"
        assert TicketPriority.CRITICAL.value == "critical"
