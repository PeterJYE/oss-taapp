"""Shared, standardized API interface for Ticketing vertical.

This module defines the standardized interface that all ticketing implementations
across teams must expose for cross-vertical integration. This is the contract
that enables interoperability between Chat, AI, and Ticketing services.
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class TicketStatus(StrEnum):
    """Enumeration of possible ticket statuses.

    This is the standardized status enum required by the shared interface.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Ticket(ABC):
    """Abstract representation of a Ticket.

    This is the minimal ticket interface required by the shared standard.
    Implementations may have additional fields internally, but must expose
    at least these properties.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for the ticket."""
        raise NotImplementedError

    @property
    @abstractmethod
    def title(self) -> str:
        """The title of the ticket."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """The detailed description of the ticket."""
        raise NotImplementedError

    @property
    @abstractmethod
    def status(self) -> TicketStatus:
        """The current status of the ticket."""
        raise NotImplementedError

    @property
    @abstractmethod
    def assignee(self) -> str | None:
        """The ID of the user assigned to the ticket, if any."""
        raise NotImplementedError


class TicketInterface(ABC):
    """The contract for Ticketing services.

    This is the standardized interface that enables cross-vertical integration.
    All ticketing implementations must provide these methods to ensure
    compatibility with Chat and AI services.
    """

    @abstractmethod
    def create_ticket(
        self,
        title: str,
        description: str,
        assignee: str | None = None,
    ) -> Ticket:
        """Create a new ticket.

        Args:
            title: Brief title describing the ticket
            description: Detailed description of the ticket
            assignee: Optional user ID to assign the ticket to

        Returns:
            The newly created Ticket instance

        Raises:
            ValueError: If title or description are invalid
            Exception: If ticket creation fails

        """
        raise NotImplementedError

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Retrieve a ticket by its ID.

        Args:
            ticket_id: Unique identifier of the ticket to retrieve

        Returns:
            The Ticket instance if found, None otherwise

        Raises:
            Exception: If retrieval operation fails

        """
        raise NotImplementedError

    @abstractmethod
    def search_tickets(
        self,
        query: str | None = None,
        status: TicketStatus | None = None,
    ) -> list[Ticket]:
        """Search for tickets based on query and/or status.

        Args:
            query: Optional text query to search in title/description
            status: Optional status filter

        Returns:
            List of Ticket instances matching the criteria

        Raises:
            Exception: If search operation fails

        """
        raise NotImplementedError

    @abstractmethod
    def update_ticket(
        self,
        ticket_id: str,
        status: TicketStatus | None = None,
        title: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
    ) -> Ticket:
        """Update a ticket's details.

        Args:
            ticket_id: Unique identifier of the ticket to update
            status: New status (optional)
            title: New title (optional)
            description: New description (optional)
            assignee: New assignee (optional)

        Returns:
            The updated Ticket instance

        Raises:
            ValueError: If provided values are invalid
            Exception: If update operation fails or ticket not found

        """
        raise NotImplementedError

    @abstractmethod
    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket. Returns True if successful.

        Args:
            ticket_id: Unique identifier of the ticket to delete

        Returns:
            True if the ticket was deleted, False if it wasn't found

        Raises:
            Exception: If deletion operation fails

        """
        raise NotImplementedError
