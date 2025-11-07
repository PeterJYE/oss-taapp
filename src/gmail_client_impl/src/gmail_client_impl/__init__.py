"""Public exports for the Gmail client implementation package.

On import, this module automatically registers the concrete Gmail client and
message factory with the abstract `mail_client_api` package so tests that rely
on side-effectful imports (dependency injection) succeed without explicitly
calling a register() function.
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


def _auto_register() -> None:
    """Automatically wire concrete implementations into abstract factories.

    Idempotent and safe to call multiple times.
    """
    _api.get_client = get_client_impl  # type: ignore[attr-defined]
    try:
        msg_mod = importlib.import_module("mail_client_api.message")
        setattr(msg_mod, "get_message", get_message_impl)
    except Exception:
        # If the shim module layout differs, attempt inner src layout
        try:
            inner_mod = importlib.import_module("mail_client_api.src.mail_client_api.message")
            setattr(inner_mod, "get_message", get_message_impl)
        except Exception:
            pass


def register() -> None:  # noqa: D401
    """Compatibility manual registration entrypoint (calls auto-register)."""
    _auto_register()


# Perform automatic registration on import
_auto_register()

__all__ = [
    "GmailClient",
    "GmailMessage",
    "get_client_impl",
    "get_message_impl",
    "register",
]
