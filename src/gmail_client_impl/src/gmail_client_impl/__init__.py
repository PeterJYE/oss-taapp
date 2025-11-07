"""Public exports for the Gmail client implementation package.

This package exposes explicit `register()` to bind concrete implementations to
the abstract `mail_client_api` factories. Importing this package DOES NOT
modify global factories; tests can opt-in by calling `gmail_client_impl.register()`.
"""

from gmail_client_impl.gmail_impl import (  # noqa: PLC0415
    GmailClient as GmailClient,
    get_client_impl as get_client_impl,
)
from gmail_client_impl.message_impl import (  # noqa: PLC0415
    GmailMessage as GmailMessage,
    get_message_impl as get_message_impl,
)

import importlib
import mail_client_api as _api  # noqa: PLC0415


def _bind_factories() -> None:
    """Wire concrete implementations into abstract factories (idempotent)."""
    _api.get_client = get_client_impl  # type: ignore[attr-defined]
    try:
        msg_mod = importlib.import_module("mail_client_api.message")
        setattr(msg_mod, "get_message", get_message_impl)
    except Exception:
        try:
            inner_mod = importlib.import_module("mail_client_api.src.mail_client_api.message")
            setattr(inner_mod, "get_message", get_message_impl)
        except Exception:
            pass


def register() -> None:  # noqa: D401
    """Manually bind concrete implementations to abstract factories."""
    _bind_factories()

__all__ = [
    "GmailClient",
    "GmailMessage",
    "get_client_impl",
    "get_message_impl",
    "register",
]
