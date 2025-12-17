"""Expose route modules for convenient imports."""

from openai_client_service.src.openai_client_service.routes import ai, oauth

__all__ = ["ai", "oauth"]
