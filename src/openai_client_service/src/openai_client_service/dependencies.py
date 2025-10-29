"""FastAPI dependencies for OpenAI Client Service."""

from fastapi import Header, HTTPException, status


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
