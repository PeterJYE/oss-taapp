"""Core mail client contract definitions and factory placeholder."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import suppress

from .message import Message

from typing import TYPE_CHECKING, Callable, Any, cast


class Client(ABC):
    """Abstract base class representing a mail client for email operations."""

    @abstractmethod
    def get_message(self, message_id: str) -> Message:
        """Return a message by its ID."""
        raise NotImplementedError

    @abstractmethod
    def delete_message(self, message_id: str) -> bool:
        """Delete a message by its ID."""
        raise NotImplementedError

    @abstractmethod
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read by its ID."""
        raise NotImplementedError

    @abstractmethod
    def get_messages(self, max_results: int = 10) -> Iterator[Message]:
        """Return an iterator of messages from the inbox."""
        raise NotImplementedError


def get_client(*, interactive: bool = False) -> Client:
    """Return an instance of a Mail Client.

    Strategy:
    1. Attempt to import a concrete implementation (gmail_client_impl). Its
       module import may (env-gated) replace this factory at the module level.
    2. If replacement occurred during this call, delegate to the new factory.
    3. Otherwise raise NotImplementedError to signal no implementation loaded.
    """
    with suppress(Exception):  # pragma: no cover - optional dependency path
        import gmail_client_impl  # noqa: F401, PLC0415

    # After the import, check whether the module-level name now points to a
    # different function object (implementation factory). If so, delegate.
    new_factory = globals().get("get_client")
    if new_factory is not get_client:
        # Narrow type: expect a callable returning Client
        impl = cast(Callable[..., Client], new_factory)
        return impl(interactive=interactive)

    err = "No mail client implementation registered"
    raise NotImplementedError(err)
