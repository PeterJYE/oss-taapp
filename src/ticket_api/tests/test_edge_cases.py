"""Additional edge case tests for ticket API."""

from dataclasses import FrozenInstanceError  # Used in test_ticket_immutability
from uuid import uuid4

import pytest

from ticket_api.ticket_impl.models import Comment, Ticket, TicketPriority

# Constants for boundary values
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_COMMENT_LENGTH = 2000
EXPECTED_COMMENT_COUNT = 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_ticket_with_unicode_content(self) -> None:
        """Test ticket with unicode characters."""
        ticket = Ticket(
            title="Bug with émojis",
            description="Unicode test: café, naïve, résumé",
            reporter="test@example.com",
        )
        assert "émojis" in ticket.title
        assert "café" in ticket.description

    def test_ticket_boundary_lengths(self) -> None:
        """Test boundary conditions for field lengths."""
        # Test maximum allowed lengths
        max_title = "x" * MAX_TITLE_LENGTH
        max_description = "x" * MAX_DESCRIPTION_LENGTH

        ticket = Ticket(
            title=max_title,
            description=max_description,
            reporter="test@example.com",
        )
        assert len(ticket.title) == MAX_TITLE_LENGTH
        assert len(ticket.description) == MAX_DESCRIPTION_LENGTH

    def test_comment_boundary_length(self) -> None:
        """Test comment with maximum allowed length."""
        max_content = "x" * MAX_COMMENT_LENGTH

        comment = Comment(
            ticket_id=uuid4(),
            author="test@example.com",
            content=max_content,
        )
        assert len(comment.content) == MAX_COMMENT_LENGTH

    def test_ticket_priority_levels(self) -> None:
        """Test all priority levels."""
        priorities = [
            TicketPriority.LOW,
            TicketPriority.MEDIUM,
            TicketPriority.HIGH,
            TicketPriority.CRITICAL,
        ]

        for priority in priorities:
            ticket = Ticket(
                title=f"Priority {priority.value} test",
                description="Testing priority levels",
                reporter="test@example.com",
                priority=priority,
            )
            assert ticket.priority == priority

    def test_empty_comments_list(self) -> None:
        """Test ticket with no comments."""
        ticket = Ticket(
            title="No comments",
            description="Testing empty comments",
            reporter="test@example.com",
        )
        assert len(ticket.comments) == 0

    def test_ticket_with_minimal_fields(self) -> None:
        """Test ticket with minimum required fields."""
        ticket = Ticket(
            title="A",
            description="B",
            reporter="a@b.c",
        )
        assert ticket.title == "A"
        assert ticket.description == "B"
        assert ticket.reporter == "a@b.c"

    def test_ticket_immutability(self) -> None:
        """Test that tickets are immutable frozen dataclasses."""
        ticket = Ticket(
            title="Immutable test",
            description="Testing immutability",
            reporter="test@example.com",
        )

        # Verify the ticket cannot be modified - frozen dataclasses raise
        # FrozenInstanceError on attribute assignment. This assignment intentionally
        # violates the read-only property to test immutability at runtime.
        with pytest.raises(FrozenInstanceError):
            ticket.title = "Modified"  # type: ignore[misc]
