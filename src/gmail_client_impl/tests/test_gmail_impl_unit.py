import pytest
from unittest.mock import MagicMock, patch
from gmail_client_impl.gmail_impl import GmailClient
from gmail_client_impl.message_impl import GmailMessage


@pytest.fixture
def mock_service():
    """Mock Gmail API service with nested users/messages calls."""
    mock_service = MagicMock()
    mock_users = mock_service.users.return_value
    mock_messages = mock_users.messages.return_value
    mock_messages.get.return_value.execute.return_value = {"id": "123", "raw": "SGVsbG8gd29ybGQ="}
    mock_messages.list.return_value.execute.return_value = {"messages": [{"id": "1"}, {"id": "2"}]}
    mock_messages.delete.return_value.execute.return_value = {}
    mock_messages.modify.return_value.execute.return_value = {}
    return mock_service


def test_init_with_service(mock_service):
    """Ensure GmailClient uses provided service and skips auth."""
    client = GmailClient(service=mock_service)
    assert client.service == mock_service


def test_interactive_auth(monkeypatch, tmp_path):
    mock_creds = MagicMock()
    mock_creds.valid = True

    # make TOKEN_PATH point to a temp file so path checks are harmless
    monkeypatch.setattr(GmailClient, "TOKEN_PATH", str(tmp_path / "token.json"))

    # stub interactive flow to return our creds
    monkeypatch.setattr(
        GmailClient, "_run_interactive_flow", lambda self, p: mock_creds
    )

    # prevent real file I/O during init
    monkeypatch.setattr(GmailClient, "_save_token", lambda self, c, p: None)

    # also stub build() so discovery client isn't created
    monkeypatch.setattr("gmail_client_impl.gmail_impl.build", lambda *a, **k: MagicMock())

    # should not raise; proves interactive path invoked
    GmailClient(service=None, interactive=True)


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_get_message_returns_message(mock_get_message, mock_service):
    """Ensure get_message calls Gmail API and wraps result in a GmailMessage."""
    mock_get_message.return_value = GmailMessage("123", "SGVsbG8=")
    client = GmailClient(service=mock_service)
    msg = client.get_message("123")
    assert isinstance(msg, GmailMessage)
    mock_get_message.assert_called_once_with(msg_id="123", raw_data="SGVsbG8gd29ybGQ=")


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_delete_message_success(mock_get_message, mock_service):
    """Ensure delete_message returns True if Gmail API delete succeeds."""
    mock_msg = MagicMock()
    mock_msg.subject = "Hello"
    mock_get_message.return_value = mock_msg
    client = GmailClient(service=mock_service)
    result = client.delete_message("xyz")
    assert result is True


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_delete_message_failure(mock_get_message, mock_service):
    """Ensure delete_message returns False when Gmail API delete fails."""
    mock_msg = MagicMock()
    mock_msg.subject = "Failing"
    mock_get_message.return_value = mock_msg
    mock_service.users.return_value.messages.return_value.delete.return_value.execute.side_effect = Exception("API error")
    client = GmailClient(service=mock_service)
    result = client.delete_message("xyz")
    assert result is False


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_mark_as_read_success(mock_get_message, mock_service):
    """Ensure mark_as_read returns True when modify() executes."""
    client = GmailClient(service=mock_service)
    assert client.mark_as_read("abc") is True


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_mark_as_read_failure(mock_get_message, mock_service):
    """Ensure mark_as_read returns False when modify() raises an error."""
    mock_service.users.return_value.messages.return_value.modify.return_value.execute.side_effect = Exception("Bad modify")
    client = GmailClient(service=mock_service)
    assert client.mark_as_read("abc") is False


@patch("gmail_client_impl.gmail_impl.message.get_message")
def test_get_messages_yields_messages(mock_get_message, mock_service):
    """Ensure get_messages yields multiple GmailMessage instances."""
    mock_get_message.side_effect = lambda msg_id, raw_data: GmailMessage(msg_id, raw_data)
    client = GmailClient(service=mock_service)
    msgs = list(client.get_messages(max_results=2))
    assert len(msgs) == 2
    assert all(isinstance(m, GmailMessage) for m in msgs)

