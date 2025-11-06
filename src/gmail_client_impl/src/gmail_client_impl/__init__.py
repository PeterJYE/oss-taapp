"""Public exports for the Gmail client implementation package."""

from gmail_client_impl.gmail_impl import (
    GmailClient as GmailClient,
    get_client_impl as get_client_impl,
)
from gmail_client_impl.gmail_impl import (
    register as _register_client,
)
from gmail_client_impl.message_impl import (
    GmailMessage as GmailMessage,
    get_message_impl as get_message_impl,
)
from gmail_client_impl.message_impl import (
    register as _register_message,
)


def register() -> None:
    """Register the Gmail client and message implementations."""
    _register_client()
    _register_message()

    # Ensure abstract factories point to concrete implementations
    import importlib
    import mail_client_api as _api

    _api.get_client = get_client_impl
    try:
        m = importlib.import_module("mail_client_api.message")
        setattr(m, "get_message", get_message_impl)
    except Exception:
        pass

__all__ = [
    "GmailClient",
    "GmailMessage",
    "get_client_impl",
    "get_message_impl",
    "register",
]
