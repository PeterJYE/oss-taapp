"""Additional tests to cover remaining lines in adapter.py."""

from unittest.mock import Mock

from chat_api.chat_adapter.adapter import ChatAdapter, SlackMessageAdapter


def test_adapter_send_message_exception() -> None:
    """Test send_message exception handling (line 82-83)."""
    mock_client = Mock()
    mock_client.post_message.side_effect = ValueError("Error")
    adapter = ChatAdapter(mock_client)
    result = adapter.send_message("channel", "message")
    assert result is False


def test_adapter_send_message_success() -> None:
    """Test send_message success (lines 79-85)."""
    mock_client = Mock()
    mock_message = Mock()
    mock_message.id = "M123"
    mock_client.post_message.return_value = mock_message
    adapter = ChatAdapter(mock_client)
    result = adapter.send_message("channel", "message")
    assert result is True


def test_adapter_get_messages_exception() -> None:
    """Test get_messages exception handling (line 102-103)."""
    mock_client = Mock()
    mock_client.get_channel_history.side_effect = RuntimeError("Error")
    adapter = ChatAdapter(mock_client)
    messages = adapter.get_messages("channel")
    assert messages == []


def test_adapter_get_messages_success() -> None:
    """Test get_messages success (lines 98-101)."""
    mock_client = Mock()
    mock_message = Mock()
    mock_message.id = "M123"
    mock_message.ts = "123456.789"
    mock_message.text = "test message"
    mock_client.get_channel_history.return_value = [mock_message]
    adapter = ChatAdapter(mock_client)
    messages = adapter.get_messages("channel")
    assert len(messages) == 1
    assert messages[0].id == "M123"


def test_adapter_delete_message_exception() -> None:
    """Test delete_message exception handling (line 118-119)."""
    mock_client = Mock()
    mock_client.delete_message.side_effect = ConnectionError("Error")
    adapter = ChatAdapter(mock_client)
    result = adapter.delete_message("channel", "message")
    assert result is False


def test_adapter_delete_message_success() -> None:
    """Test delete_message success (line 117)."""
    mock_client = Mock()
    mock_client.delete_message.return_value = True
    adapter = ChatAdapter(mock_client)
    result = adapter.delete_message("channel", "message")
    assert result is True


def test_slack_message_adapter_id_with_ts() -> None:
    """Test SlackMessageAdapter.id when id is empty, uses ts (line 33)."""
    mock_slack_msg = Mock()
    mock_slack_msg.id = ""
    mock_slack_msg.ts = "123456.789"
    adapter = SlackMessageAdapter(mock_slack_msg)
    assert adapter.id == "123456.789"


def test_slack_message_adapter_sender_id() -> None:
    """Test SlackMessageAdapter.sender_id returns empty string (line 49)."""
    mock_slack_msg = Mock()
    adapter = SlackMessageAdapter(mock_slack_msg)
    assert adapter.sender_id == ""

