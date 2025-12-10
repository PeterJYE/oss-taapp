"""Chat Adapter: Implements ChatInterface by wrapping SlackClient from chat_impl.

This adapter bridges the gap between the shared ChatInterface and the concrete
SlackClient implementation, allowing services to use only the shared interface.
"""

from __future__ import annotations

# These imports are needed at runtime, not just for type checking
from chat_api.chat_impl.src.slack_impl import SlackClient  # noqa: TC001
from chat_api.chat_impl.src.slack_impl.slack_client import Message as SlackMessage  # noqa: TC001
from chat_api.chat_interface import ChatInterface
from chat_api.chat_interface import Message as ChatMessage

__all__ = ["ChatAdapter"]


class SlackMessageAdapter(ChatMessage):
    """Adapter that wraps Slack's Message to implement the shared Message ABC."""

    def __init__(self, slack_message: SlackMessage) -> None:
        """Initialize with a Slack Message object.

        Args:
            slack_message: The Slack Message object from slack_impl

        """
        self._slack_message = slack_message

    @property
    def id(self) -> str:
        """Return the message ID (uses ts if id is empty)."""
        return self._slack_message.id or self._slack_message.ts

    @property
    def content(self) -> str:
        """Return the message text content."""
        return self._slack_message.text

    @property
    def sender_id(self) -> str:
        """Return the sender ID.

        Note: SlackClient's Message doesn't have sender_id, so we return
        an empty string. This can be enhanced if sender_id is added to
        the Slack Message model.
        """
        # Note: sender_id not available in SlackClient.Message
        return ""


class ChatAdapter(ChatInterface):
    """Adapter that implements ChatInterface using SlackClient.

    This adapter wraps the SlackClient from chat_impl and exposes only
    the methods defined in the shared ChatInterface.
    """

    def __init__(self, slack_client: SlackClient) -> None:
        """Initialize the adapter with a SlackClient instance.

        Args:
            slack_client: The SlackClient to wrap

        """
        self._client = slack_client

    def send_message(self, channel_id: str, content: str) -> bool:
        """Send a message to a specific channel.

        Args:
            channel_id: The channel ID to send the message to
            content: The message content/text

        Returns:
            True if the message was sent successfully, False otherwise

        """
        try:
            result = self._client.post_message(channel=channel_id, text=content)
            # post_message returns a Message object, so if we get here, it succeeded
        except (ValueError, RuntimeError, ConnectionError, OSError):
            return False
        else:
            return result is not None

    def get_messages(self, channel_id: str, limit: int = 10) -> list[ChatMessage]:
        """Read the last N messages from a channel.

        Args:
            channel_id: The channel ID to read messages from
            limit: Maximum number of messages to retrieve (default: 10)

        Returns:
            List of Message objects implementing the shared Message ABC

        """
        try:
            slack_messages = self._client.get_channel_history(channel=channel_id, limit=limit)
            # Convert Slack Messages to shared Message ABC
            return [SlackMessageAdapter(msg) for msg in slack_messages]
        except (ValueError, RuntimeError, ConnectionError, OSError):
            return []

    def delete_message(self, channel_id: str, message_id: str) -> bool:
        """Delete a specific message.

        Args:
            channel_id: The channel ID where the message exists
            message_id: The message ID (or timestamp) to delete

        Returns:
            True if the message was deleted successfully, False otherwise

        """
        try:
            return self._client.delete_message(channel=channel_id, message_id=message_id)
        except (ValueError, RuntimeError, ConnectionError, OSError):
            return False

