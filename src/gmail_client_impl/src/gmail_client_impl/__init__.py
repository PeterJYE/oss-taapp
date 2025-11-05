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


# Auto-register on import so the abstract API factories are wired by default.
try:  # pragma: no cover - trivial import-time wiring
    register()
except Exception:
    # In environments where dependencies are missing, importing this package
    # shouldn't hard-crash the process; tests that need registration can call
    # gmail_client_impl.register() explicitly.
    pass
