"""Custom exceptions for the Ticket API."""

from uuid import UUID


class ServiceError(Exception):
    """Base exception for service-level errors in the ticket system."""


class TicketNotFoundError(ServiceError):
    """Exception raised when a ticket is not found."""

    def __init__(self, ticket_id: UUID) -> None:
        """Initialize with ticket ID."""
        self.ticket_id = ticket_id
        super().__init__(f"Ticket {ticket_id} not found")
