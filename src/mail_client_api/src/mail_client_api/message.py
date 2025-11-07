"""Message contract - Core message representation."""

from abc import ABC, abstractmethod
from contextlib import suppress


class Message(ABC):
    """Abstract base class representing an email message."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the unique identifier of the message."""
        raise NotImplementedError

    @property
    @abstractmethod
    def from_(self) -> str:
        """Return the sender's email address."""
        raise NotImplementedError

    @property
    @abstractmethod
    def to(self) -> str:
        """Return the recipient's email address."""
        raise NotImplementedError

    @property
    @abstractmethod
    def date(self) -> str:
        """Return the date the message was sent."""
        raise NotImplementedError

    @property
    @abstractmethod
    def subject(self) -> str:
        """Return the subject line of the message."""
        raise NotImplementedError

    @property
    @abstractmethod
    def body(self) -> str:
        """Return the plain text content of the message."""
        raise NotImplementedError


def get_message(_msg_id: str, _raw_data: str) -> Message:
    """Return a concrete message instance (implementation registered externally).

    Performs a lazy import to trigger implementation auto-registration. Always
    raises NotImplementedError until an implementation rebinds this name.
    """
    with suppress(Exception):  # pragma: no cover - optional dependency path
        import gmail_client_impl  # noqa: F401, PLC0415
    err = "No message implementation registered"
    raise NotImplementedError(err)
