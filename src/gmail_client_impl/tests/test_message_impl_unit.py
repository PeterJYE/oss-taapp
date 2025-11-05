import base64
import email

from gmail_client_impl.message_impl import GmailMessage, get_message_impl, register


def make_email_bytes():
    msg = email.message.EmailMessage()
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Subject"] = "Test Email"
    msg["Date"] = "Mon, 19 Oct 2025 10:00:00 -0000"
    msg.set_content("Hello Gmail!")
    return msg.as_bytes()


def test_valid_message_decoding():
    """Ensure GmailMessage correctly decodes base64-encoded raw data."""
    raw_data = base64.urlsafe_b64encode(make_email_bytes()).decode("utf-8")
    gm = GmailMessage(msg_id="123", raw_data=raw_data)

    assert gm.id == "123"
    assert gm.from_ == "alice@example.com"
    assert gm.to == "bob@example.com"
    assert gm.subject == "Test Email"
    assert gm.date == "10/19/2025"
    assert "Hello Gmail" in gm.body


def test_invalid_base64_triggers_error_message():
    """Invalid base64 input should produce a fallback parsed message."""
    gm = GmailMessage(msg_id="1", raw_data="not_base64")
    assert gm.subject == GmailMessage.ERROR_PARSING_MESSAGE
    assert gm.from_ == GmailMessage.UNKNOWN_SENDER
    assert gm.to == GmailMessage.UNKNOWN_RECIPIENT
    assert gm.date == GmailMessage.UNKNOWN_DATE


def test_is_binary_garbage_detection():
    gm = GmailMessage("id", base64.urlsafe_b64encode(b"simple text").decode())
    assert gm._is_binary_garbage(b"Hello") is False
    assert gm._is_binary_garbage(b"\x00\x01\x02\x03\x04\xff") is True


def test_get_message_impl_returns_gmail_message():
    msg = get_message_impl("999", base64.urlsafe_b64encode(make_email_bytes()).decode())
    assert isinstance(msg, GmailMessage)
    assert msg.id == "999"


def test_register_overrides_message_getter(monkeypatch):
    """Ensure register() patches mail_client_api.message.get_message."""
    import importlib
    import mail_client_api

    importlib.reload(mail_client_api.message)
    original = mail_client_api.message.get_message

    register()
    assert mail_client_api.message.get_message != original
    assert isinstance(
        mail_client_api.message.get_message(
            "1", base64.urlsafe_b64encode(make_email_bytes()).decode()
        ),
        GmailMessage,
    )
