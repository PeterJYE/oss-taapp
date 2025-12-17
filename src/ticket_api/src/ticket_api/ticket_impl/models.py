"""Data models for the ticket API using dataclasses.

This module defines the core data structures used throughout the ticketing system.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


class TicketStatus(str, Enum):
    """Enumeration of possible ticket statuses."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Enumeration of ticket priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Comment:
    """Represents a comment on a ticket.

    Comments are immutable once created and track who made the comment
    and when it was created.
    """

    ticket_id: UUID = field()
    author: str = field()
    content: str = field()
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Ticket:
    """Represents a support ticket in the system.

    Tickets track issues, requests, or tasks with associated metadata
    like status, priority, and timestamps.
    """

    title: str = field()
    description: str = field()
    reporter: str = field()
    id: UUID = field(default_factory=uuid4)
    status: TicketStatus = field(default=TicketStatus.OPEN)
    priority: TicketPriority = field(default=TicketPriority.MEDIUM)
    assignee: str | None = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    comments: list[Comment] = field(default_factory=list)
