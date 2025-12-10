"""Ticket API package - Shared interface for cross-vertical integration.

This package defines the standardized interface for ticket operations:
- TicketInterface: The contract for ticketing services
- Ticket: Abstract ticket representation
- TicketStatus: Enumeration of ticket statuses
- StandardizedTicketAdapter: Adapter to expose TicketInterface from implementations
"""

from .ticket_adapter import StandardizedTicketAdapter
from .ticket_interface import Ticket, TicketInterface, TicketStatus

__all__ = [
    "StandardizedTicketAdapter",
    "Ticket",
    "TicketInterface",
    "TicketStatus",
]
