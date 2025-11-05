"""shim module that re-exports the real implementation under the src layout.

This allows tests and other packages to import ``mail_client_api.client`` while
the actual implementation lives under ``src/mail_client_api/src/mail_client_api``.
"""
from .src.mail_client_api.client import *  # noqa: F403

__all__ = [name for name in dir() if not name.startswith("_")]
