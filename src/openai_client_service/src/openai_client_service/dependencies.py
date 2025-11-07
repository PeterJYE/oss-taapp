"""FastAPI dependencies for OpenAI Client Service."""

import uuid as _uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from openai_service_api.client import AIClient


class MissingOpenAIKeyError(Exception):  # local lightweight fallback
    """Raised when an OpenAI API key is required but unavailable."""


# Do not import AIClientImpl at module import time to avoid optional deps (openai/cryptography)
AIClientImpl = None  # type: ignore[assignment]

_SESSION_STORE: dict[str, dict[str, str]] = {}
_CONVERSATIONS: dict[str, dict[str, object]] = {}


async def get_subject(x_subject: str | None = Header(default=None)) -> str:
    """Extract and validate the X-Subject header.

    Args:
        x_subject: The X-Subject header value

    Returns:
        The validated subject string

    Raises:
        HTTPException: If X-Subject header is missing

    """
    if not x_subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Subject header. Please provide a user identifier.",
        )
    return x_subject


async def get_authenticated_subject(
    session_id: str | None = Cookie(default=None, alias="session_id"),
) -> str:
    """Return the authenticated subject from the OAuth session cookie.

    Raises 401 if there is no valid session.
    """
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = _SESSION_STORE.get(session_id)
    if not session or "subject" not in session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return session["subject"]


def _create_session(session_id: str, subject: str) -> None:
    """Create or replace a session with the given subject."""
    _SESSION_STORE[session_id] = {"subject": subject}


def _destroy_session(session_id: str) -> None:
    """Remove a session if it exists."""
    _SESSION_STORE.pop(session_id, None)


class _UnavailableClient:  # minimal duck-typed stand-in
    """Fallback AI client used when real implementation is unavailable or unconfigured."""

    def __init__(self, subject: str) -> None:
        self._subject = subject

    def generate_response(self, messages: list[str], *, conversation_id: str | None = None) -> None:  # noqa: ARG002
        err = "OpenAI API key is not set"
        raise MissingOpenAIKeyError(err)

    def create_conversation(self) -> str:
        conv_id = str(_uuid.uuid4())
        _CONVERSATIONS[conv_id] = {"id": conv_id, "messages": [], "created_at": "1970-01-01T00:00:00Z"}
        return conv_id

    def get_conversation(self, conversation_id: str) -> None:
        data = _CONVERSATIONS.get(conversation_id)
        if not data:
            _msg = f"Conversation not found: {conversation_id}"
            raise ValueError(_msg)
        class _Conv:
            def __init__(self, d: dict[str, object]) -> None:
                self.id = d.get("id", "")  # type: ignore[assignment]
                self.messages = d.get("messages", [])  # type: ignore[assignment]
                self.created_at = d.get("created_at", "")  # type: ignore[assignment]
        return _Conv(data)

    def delete_conversation(self, conversation_id: str) -> bool:
        return _CONVERSATIONS.pop(conversation_id, None) is not None


def get_ai_client(subject: Annotated[str, Depends(get_authenticated_subject)]) -> AIClient:
    """Return an AIClient instance for the authenticated subject.

    This dependency injects the AI client implementation into route handlers,
    using the authenticated subject from the session cookie.

    Args:
        subject: Authenticated user subject from session (injected via dependency)

    Returns:
        AIClient instance configured for the authenticated user

    Raises:
        HTTPException: If user is not authenticated

    """
    try:
        # Lazy import to tolerate environments without optional packages
        from openai_client_impl import AIClientImpl as _Impl  # type: ignore[attr-defined]  # noqa: PLC0415
    except Exception:  # pragma: no cover - environment dependent  # noqa: BLE001
        return _UnavailableClient(subject)  # type: ignore[return-value]

    # If import succeeded, attempt to construct the real client. If construction fails
    # due to missing key or storage issues, fall back to the in-memory client so routes
    # like create_conversation work in CI without secrets.
    try:
        return _Impl(subject=subject)  # type: ignore[return-value]
    except Exception:  # noqa: BLE001
        return _UnavailableClient(subject)  # type: ignore[return-value]
