"""Public exports for the Gmail client implementation package."""

from gmail_client_impl.gmail_impl import (
    GmailClient,
    get_client_impl,
)
from gmail_client_impl.gmail_impl import (
    register as _register_client,
)
from gmail_client_impl.message_impl import (
    GmailMessage,
    get_message_impl,
)
from gmail_client_impl.message_impl import (
    register as _register_message,
)


def register() -> None:
    """Register the Gmail client and message implementations."""
    _register_client()
    _register_message()


# Note: Previously this package auto-registered its implementations at import-time.
# That behavior causes cross-test pollution (overriding the abstract API globally
# before some tests expect the default NotImplementedError). Tests should import
# this package and call `register()` explicitly when they want to activate the
# Gmail implementations.
