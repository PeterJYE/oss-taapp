"""FastAPI dependencies for OpenAI Client Service."""

from fastapi import Cookie, Header, HTTPException, status

_SESSION_STORE: dict[str, dict[str, str]] = {}


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
    x_subject: str | None = Header(default=None),
) -> str:
    """Return the authenticated subject from the OAuth session cookie.

    Raises 401 if there is no valid session. Intended to replace the
    header-based subject once OAuth is enabled.
    """
    if session_id:
        session = _SESSION_STORE.get(session_id)
        if session and "subject" in session:
            return session["subject"]

    if x_subject:
        return x_subject
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def _create_session(session_id: str, subject: str) -> None:
    """Create or replace a session with the given subject."""
    _SESSION_STORE[session_id] = {"subject": subject}


def _destroy_session(session_id: str) -> None:
    """Remove a session if it exists."""
    _SESSION_STORE.pop(session_id, None)
