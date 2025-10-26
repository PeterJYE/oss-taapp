"""Mail Client Service - FastAPI wrapper for mail client operations.

This package provides a RESTful API service that wraps the existing mail client
components. It acts as a thin wrapper around the gmail_client_impl package and
exposes email operations through HTTP endpoints.

Usage:
    from mail_client_service import app
    # Run with: uvicorn mail_client_service:app --reload
"""

from . import main
