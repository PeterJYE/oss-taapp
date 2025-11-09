"""Tests ensuring the mail_client_api package shim exposes expected symbols."""

import mail_client_api


def test_exports_and_modules() -> None:
    """Ensure the package shim exposes expected symbols and modules."""
    assert hasattr(mail_client_api, "get_client")
    assert hasattr(mail_client_api, "Message")
    assert hasattr(mail_client_api, "client")
    assert hasattr(mail_client_api, "message")

    # Ensure module aliases match the inner package.
    inner_client = mail_client_api.client
    inner_message = mail_client_api.message
    assert inner_client is not None
    assert inner_message is not None

