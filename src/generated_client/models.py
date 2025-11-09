"""Shim module exposing models from the inner generated client package.

This file allows code to `import generated_client.models` even though the
actual generated code lives under `generated_client.mail_client_service_client.models`.
"""

from generated_client.mail_client_service_client.models import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]
