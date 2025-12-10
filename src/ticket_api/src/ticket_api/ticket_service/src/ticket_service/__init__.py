"""Ticket Service - FastAPI service for ticket management.

This service exposes the ticket API implementation over HTTP endpoints,
including OAuth 2.0 authentication flow and core ticket operations.
"""

__version__ = "0.1.0"

from ticket_service.main import app

__all__ = ["__version__", "app"]
