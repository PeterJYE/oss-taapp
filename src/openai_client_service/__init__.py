"""Expose key components of the OpenAI client service package."""

from .src.openai_client_service import dependencies, routes
from .src.openai_client_service.main import app

__all__ = ["app", "dependencies", "routes"]
