"""Compatibility shim for the generated OpenAPI client package.

This module re-exports the inner `mail_client_service_client` package so code
that imports `generated_client` (legacy import path used in this repo) will
continue to work during tests and development.
"""
from .mail_client_service_client.client import Client  # re-export main client class

# Re-export commonly used subpackages so existing imports continue to work
from .mail_client_service_client import models as models  # noqa: F401
from .mail_client_service_client import api as api  # noqa: F401
from . import mail_client_service_client as mail_client_service_client  # noqa: F401

__all__ = ["Client", "models", "api", "mail_client_service_client"]
