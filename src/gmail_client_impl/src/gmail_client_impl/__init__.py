"""Public exports for the Gmail client implementation package."""

from gmail_client_impl.gmail_impl import (
    GmailClient as GmailClient,
)
from gmail_client_impl.gmail_impl import (
    get_client as get_client,
)
from gmail_client_impl.gmail_impl import (
    get_client_impl as get_client_impl,
)
from gmail_client_impl.gmail_impl import (
    register as _register_client,
)
from gmail_client_impl.message_impl import (
    GmailMessage as GmailMessage,
)
from gmail_client_impl.message_impl import (
    get_message_impl as get_message_impl,
)
from gmail_client_impl.message_impl import (
    register as _register_message,
)


def register() -> None:
    """Register the Gmail client and message implementations."""
    _register_client()
    _register_message()
