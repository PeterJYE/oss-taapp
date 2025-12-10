"""Abstract interfaces for Chat APIs."""

from abc import ABC, abstractmethod

from .message import Message


class ChatInterface(ABC):
    """Minimal interface for sending and receiving messages."""

    @abstractmethod
    def send_message(self, channel_id: str, content: str) -> bool:
        """Send a message to a specific destination (channel/thread).

        Args:
            channel_id: The channel ID to send the message to
            content: The message content/text

        Returns:
            True if the message was sent successfully, False otherwise

        """
        raise NotImplementedError

    @abstractmethod
    def get_messages(self, channel_id: str, limit: int = 10) -> list[Message]:
        """Read the last N messages from a destination.

        Args:
            channel_id: The channel ID to read messages from
            limit: Maximum number of messages to retrieve (default: 10)

        Returns:
            List of Message objects

        """
        raise NotImplementedError

    @abstractmethod
    def delete_message(self, channel_id: str, message_id: str) -> bool:
        """Delete a specific message.

        Args:
            channel_id: The channel ID where the message exists
            message_id: The message ID (or timestamp) to delete

        Returns:
            True if the message was deleted successfully, False otherwise

        """
        raise NotImplementedError
