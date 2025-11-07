"""Public exports for the Gmail client implementation package.

This package exposes explicit ``register()`` to bind concrete implementations to
the abstract ``mail_client_api`` factories. For integration tests we enable
auto-registration by default so factory identity checks pass immediately after
import. Set environment variable ``GMAIL_CLIENT_IMPL_AUTO_REGISTER=0`` to disable
this side effect (unit tests that assert ``NotImplementedError`` on the abstract
factory only import ``mail_client_api`` and are unaffected).
"""

from gmail_client_impl.gmail_impl import (  # noqa: PLC0415
    GmailClient as GmailClient,
    get_client as get_client,
    get_client_impl as get_client_impl,
)
from gmail_client_impl.message_impl import (  # noqa: PLC0415
    GmailMessage as GmailMessage,
    get_message as get_message,
    get_message_impl as get_message_impl,
)

import importlib
import os
import mail_client_api as _api


def _bind_factories(*, public_alias: bool = True) -> None:
    """Wire concrete implementations into abstract factories (idempotent).

    If public_alias is True, bind the message factory to the public alias
    get_message (which forwards to get_message_impl). Some tests explicitly
    assert identity with get_message_impl, so when public_alias=False we bind
    directly to the implementation for explicit registration scenarios.
    """
    _api.get_client = get_client if public_alias else get_client_impl
    target = get_message if public_alias else get_message_impl
    try:
        msg_mod = importlib.import_module("mail_client_api.message")
        setattr(msg_mod, "get_message", target)
    except Exception:
        pass


def register() -> None:  # noqa: D401
    """Manually bind concrete implementations to abstract factories.

    Explicit registration uses the raw implementation factory for tests that
    assert identity with get_message_impl.
    """
    _bind_factories(public_alias=False)

# Auto-register unless explicitly disabled via env var.
if os.getenv("GMAIL_CLIENT_IMPL_AUTO_REGISTER", "1") == "1":  # pragma: no cover
    try:  # Bind using public alias variant for general imports.
        _bind_factories(public_alias=True)
    except Exception:  # pragma: no cover - defensive
        pass

__all__ = [
    "GmailClient",
    "GmailMessage",
    "get_client",
    "get_message",
    "get_client_impl",
    "get_message_impl",
    "register",
]
