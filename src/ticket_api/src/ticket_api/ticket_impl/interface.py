"""Abstract base class defining the ticket service API contract.

This module defines the interface that all ticket service implementations
must follow, ensuring consistency across different implementations.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from .models import Comment, Ticket, TicketPriority, TicketStatus


class TicketServiceAPI(ABC):
    """Abstract base class for ticket service implementations.

    This interface defines all the operations that a ticket service
    must support. Concrete implementations must provide all these methods.
    """

    @abstractmethod
    async def create_ticket(
        self,
        title: str,
        description: str,
        reporter: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: str | None = None,
    ) -> Ticket:
        """Create a new ticket in the system.

        Args:
            title: Brief title describing the ticket
            description: Detailed description of the ticket
            reporter: Username or email of the person creating the ticket
            priority: Priority level for the ticket (defaults to MEDIUM)
            assignee: Optional username or email to assign the ticket to

        Returns:
            The newly created Ticket instance

        Raises:
            ValueError: If title or description are empty
            ServiceError: If ticket creation fails

        """

    @abstractmethod
    async def get_ticket(self, ticket_id: UUID) -> Ticket | None:
        """Retrieve a ticket by its ID.

        Args:
            ticket_id: Unique identifier of the ticket to retrieve

        Returns:
            The Ticket instance if found, None otherwise

        Raises:
            ServiceError: If retrieval operation fails

        """

    @abstractmethod
    async def list_tickets(
        self,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets with optional filtering.

        Args:
            status: Filter by ticket status (optional)
            assignee: Filter by assigned person (optional)
            reporter: Filter by reporter (optional)
            limit: Maximum number of tickets to return (default: 100)
            offset: Number of tickets to skip for pagination (default: 0)

        Returns:
            List of Ticket instances matching the criteria

        Raises:
            ValueError: If limit is negative or offset is negative
            ServiceError: If listing operation fails

        """

    @abstractmethod
    async def update_ticket(
        self,
        ticket_id: UUID,
        title: str | None = None,
        description: str | None = None,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        assignee: str | None = None,
    ) -> Ticket | None:
        """Update an existing ticket.

        Note: This method intentionally accepts multiple optional parameters to allow
        atomic updates of any combination of fields. This provides a flexible API that
        avoids the need for separate methods for each field update.

        Args:
            ticket_id: Unique identifier of the ticket to update
            title: New title (optional)
            description: New description (optional)
            status: New status (optional)
            priority: New priority (optional)
            assignee: New assignee (optional)

        Returns:
            The updated Ticket instance if found and updated, None if not found

        Raises:
            ValueError: If provided values are invalid
            ServiceError: If update operation fails

        """

    @abstractmethod
    async def delete_ticket(self, ticket_id: UUID) -> bool:
        """Delete a ticket from the system.

        Args:
            ticket_id: Unique identifier of the ticket to delete

        Returns:
            True if the ticket was deleted, False if it wasn't found

        Raises:
            ServiceError: If deletion operation fails

        """

    @abstractmethod
    async def add_comment(
        self,
        ticket_id: UUID,
        author: str,
        content: str,
    ) -> Comment | None:
        """Add a comment to an existing ticket.

        Args:
            ticket_id: Unique identifier of the ticket to comment on
            author: Username or email of the comment author
            content: Comment text content

        Returns:
            The newly created Comment instance if ticket exists, None otherwise

        Raises:
            ValueError: If content is empty
            ServiceError: If comment creation fails

        """

    @abstractmethod
    async def get_ticket_comments(self, ticket_id: UUID) -> list[Comment]:
        """Retrieve all comments for a specific ticket.

        Args:
            ticket_id: Unique identifier of the ticket

        Returns:
            List of Comment instances for the ticket (empty list if ticket not found)

        Raises:
            ServiceError: If retrieval operation fails

        """

    @abstractmethod
    async def transition_status(
        self,
        ticket_id: UUID,
        new_status: TicketStatus,
    ) -> Ticket | None:
        """Transition a ticket to a new status.

        Domain-specific operation for changing ticket workflow state.

        Args:
            ticket_id: Unique identifier of the ticket
            new_status: New status to transition to

        Returns:
            Updated Ticket instance if found, None if ticket not found

        Raises:
            ValueError: If status transition is invalid
            ServiceError: If transition operation fails

        """

    @abstractmethod
    async def reassign_ticket(
        self,
        ticket_id: UUID,
        new_assignee: str,
    ) -> Ticket | None:
        """Reassign a ticket to a different person.

        Domain-specific operation for changing ticket ownership.

        Args:
            ticket_id: Unique identifier of the ticket
            new_assignee: Username or email of the new assignee

        Returns:
            Updated Ticket instance if found, None if ticket not found

        Raises:
            ValueError: If new_assignee is invalid
            ServiceError: If reassignment operation fails

        """

    @abstractmethod
    async def update_priority(
        self,
        ticket_id: UUID,
        new_priority: TicketPriority,
    ) -> Ticket | None:
        """Update a ticket's priority level.

        Domain-specific operation for changing importance level.

        Args:
            ticket_id: Unique identifier of the ticket
            new_priority: New priority level

        Returns:
            Updated Ticket instance if found, None if ticket not found

        Raises:
            ServiceError: If update operation fails

        """

    @abstractmethod
    async def update_description(
        self,
        ticket_id: UUID,
        new_description: str,
    ) -> Ticket | None:
        """Update a ticket's description.

        Domain-specific operation for updating ticket details.

        Args:
            ticket_id: Unique identifier of the ticket
            new_description: New description text

        Returns:
            Updated Ticket instance if found, None if ticket not found

        Raises:
            ValueError: If new_description is invalid
            ServiceError: If update operation fails

        """
