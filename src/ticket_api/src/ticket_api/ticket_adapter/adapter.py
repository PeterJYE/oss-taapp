"""Adapter to expose standardized TicketInterface from internal TicketServiceAPI.

This module provides a compatibility layer that translates between the standardized
shared interface (required for cross-vertical integration) and our internal
feature-rich TicketServiceAPI implementation.

Architecture:
    - Preserves all existing internal functionality (async, UUIDs, comments, priorities)
    - Exposes only the minimal standardized interface required by other verticals
    - Enables seamless integration without breaking existing code
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

# Import from ticket_impl's internal APIs
# Note: These are internal implementation details, not part of shared interface
from ticket_api.ticket_impl.interface import TicketServiceAPI
from ticket_api.ticket_impl.models import Ticket as InternalTicket
from ticket_api.ticket_impl.models import TicketStatus as InternalTicketStatus
from ticket_api.ticket_interface.shared_interface import (
    Ticket,
    TicketInterface,
)
from ticket_api.ticket_interface.shared_interface import (
    TicketStatus as SharedTicketStatus,
)


@dataclass(frozen=True)
class SimpleTicket(Ticket):
    """Simplified ticket representation implementing the shared Ticket interface.

    This class wraps our internal rich Ticket model and exposes only the
    fields required by the standardized interface. Additional fields like
    priority, reporter, timestamps, and comments remain accessible through
    the internal API but are hidden from the shared interface.
    """

    _id: str
    _title: str
    _description: str
    _status: SharedTicketStatus
    _assignee: str | None

    @property
    def id(self) -> str:
        """Unique identifier for the ticket."""
        return self._id

    @property
    def title(self) -> str:
        """The title of the ticket."""
        return self._title

    @property
    def description(self) -> str:
        """The detailed description of the ticket."""
        return self._description

    @property
    def status(self) -> SharedTicketStatus:
        """The current status of the ticket."""
        return self._status

    @property
    def assignee(self) -> str | None:
        """The ID of the user assigned to the ticket, if any."""
        return self._assignee


class StandardizedTicketAdapter(TicketInterface):
    """Adapter that exposes the standardized TicketInterface.

    This adapter wraps an internal TicketServiceAPI implementation and provides
    the standardized interface required for cross-vertical integration. It handles:
    - Converting between sync and async interfaces
    - Mapping UUIDs to/from strings
    - Translating between internal and shared status enums
    - Simplifying ticket representations
    - Providing default values for internal-only fields

    Usage:
        internal_service = TicketImpl(user_id="user123", project_key="PROJ")
        standardized_service = StandardizedTicketAdapter(internal_service)

        # Now use standardized_service with the shared interface
        ticket = standardized_service.create_ticket(
            title="Bug in login",
            description="Users cannot log in",
            assignee="dev@example.com"
        )
    """

    def __init__(self, internal: TicketServiceAPI, reporter: str = "system") -> None:
        """Initialize the adapter with an internal TicketServiceAPI implementation.

        Args:
            internal: The internal TicketServiceAPI implementation to wrap
            reporter: Default reporter to use for ticket creation (since the
                     shared interface doesn't include reporter, but our internal
                     API requires it). Defaults to "system".

        """
        self._internal = internal
        self._reporter = reporter

    def _to_simple(self, internal_ticket: InternalTicket) -> SimpleTicket:
        """Convert an internal Ticket to a SimpleTicket.

        Args:
            internal_ticket: The internal feature-rich ticket

        Returns:
            A SimpleTicket exposing only the standardized fields

        """
        # Map internal status to shared status
        status_map = {
            InternalTicketStatus.OPEN: SharedTicketStatus.OPEN,
            InternalTicketStatus.IN_PROGRESS: SharedTicketStatus.IN_PROGRESS,
            InternalTicketStatus.RESOLVED: SharedTicketStatus.CLOSED,
            InternalTicketStatus.CLOSED: SharedTicketStatus.CLOSED,
        }

        return SimpleTicket(
            _id=str(internal_ticket.id),
            _title=internal_ticket.title,
            _description=internal_ticket.description,
            _status=status_map[internal_ticket.status],
            _assignee=internal_ticket.assignee,
        )

    def _to_internal_status(
        self,
        shared_status: SharedTicketStatus,
    ) -> InternalTicketStatus:
        """Convert a shared status to internal status.

        Args:
            shared_status: Status from the standardized interface

        Returns:
            Corresponding internal status enum value

        """
        status_map = {
            SharedTicketStatus.OPEN: InternalTicketStatus.OPEN,
            SharedTicketStatus.IN_PROGRESS: InternalTicketStatus.IN_PROGRESS,
            SharedTicketStatus.CLOSED: InternalTicketStatus.CLOSED,
        }
        return status_map[shared_status]

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
        # Run the async method synchronously
        internal_ticket = asyncio.run(
            self._internal.create_ticket(
                title=title,
                description=description,
                reporter=self._reporter,
                assignee=assignee,
            ),
        )
        return self._to_simple(internal_ticket)

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Retrieve a ticket by its ID.

        Args:
            ticket_id: Unique identifier of the ticket to retrieve

        Returns:
            The Ticket instance if found, None otherwise

        Raises:
            ValueError: If ticket_id is not a valid UUID string
            Exception: If retrieval operation fails

        """
        try:
            uuid = UUID(ticket_id)
        except ValueError as e:
            msg = f"Invalid ticket ID format: {ticket_id}"
            raise ValueError(msg) from e

        internal_ticket = asyncio.run(self._internal.get_ticket(uuid))
        if internal_ticket is None:
            return None
        return self._to_simple(internal_ticket)

    def search_tickets(
        self,
        query: str | None = None,
        status: SharedTicketStatus | None = None,
    ) -> list[Ticket]:
        """Search for tickets based on query and/or status.

        Args:
            query: Optional text query to search in title/description
            status: Optional status filter

        Returns:
            List of Ticket instances matching the criteria

        Raises:
            Exception: If search operation fails

        Note:
            The query parameter is implemented using client-side filtering
            since our internal API doesn't have a direct text search parameter.
            For production use, this could be optimized with a dedicated
            search endpoint.

        """
        # Convert shared status to internal status if provided
        internal_status = None
        if status is not None:
            internal_status = self._to_internal_status(status)

        # Get tickets from internal API
        internal_tickets = asyncio.run(
            self._internal.list_tickets(status=internal_status),
        )

        # Apply text search filter if query is provided
        if query:
            query_lower = query.lower()
            internal_tickets = [
                t
                for t in internal_tickets
                if query_lower in t.title.lower() or query_lower in t.description.lower()
            ]

        # Convert to simple tickets
        return [self._to_simple(t) for t in internal_tickets]

    def update_ticket(
        self,
        ticket_id: str,
        status: SharedTicketStatus | None = None,
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
            ValueError: If ticket_id is invalid or ticket not found
            Exception: If update operation fails

        """
        try:
            uuid = UUID(ticket_id)
        except ValueError as e:
            msg = f"Invalid ticket ID format: {ticket_id}"
            raise ValueError(msg) from e

        # Convert shared status to internal status if provided
        internal_status = None
        if status is not None:
            internal_status = self._to_internal_status(status)

        internal_ticket = asyncio.run(
            self._internal.update_ticket(
                ticket_id=uuid,
                status=internal_status,
                title=title,
                description=description,
                assignee=assignee,
            ),
        )

        if internal_ticket is None:
            msg = f"Ticket not found: {ticket_id}"
            raise ValueError(msg)

        return self._to_simple(internal_ticket)

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket. Returns True if successful.

        Args:
            ticket_id: Unique identifier of the ticket to delete

        Returns:
            True if the ticket was deleted, False if it wasn't found

        Raises:
            ValueError: If ticket_id is not a valid UUID string
            Exception: If deletion operation fails

        """
        try:
            uuid = UUID(ticket_id)
        except ValueError as e:
            msg = f"Invalid ticket ID format: {ticket_id}"
            raise ValueError(msg) from e

        return asyncio.run(self._internal.delete_ticket(uuid))
