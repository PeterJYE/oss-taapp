"""Abstract representation of a chat message."""

from abc import ABC, abstractmethod


class Message(ABC):
    """Abstract wrapper around a platform-specific message."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for the message."""
        raise NotImplementedError

    @property
    @abstractmethod
    def content(self) -> str:
        """The actual text content of the message."""
        raise NotImplementedError

    @property
    @abstractmethod
    def sender_id(self) -> str:
        """The ID of the user who sent the message."""
        raise NotImplementedError
