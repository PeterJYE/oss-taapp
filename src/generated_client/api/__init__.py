"""Shim to expose generated API modules at `generated_client.api`.

This mirrors the structure under mail_client_service_client.api so imports like
`from generated_client.api.default import ...` continue to work.
"""

from ..mail_client_service_client.api import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]
