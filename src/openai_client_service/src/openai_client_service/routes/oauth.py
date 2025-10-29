"""Authentication routes for OpenAI Client Service."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openai_client_impl import set_openai_key

router = APIRouter()


class SetKeyRequest(BaseModel):
    """Request model for setting OpenAI API key."""

    subject: str
    api_key: str


@router.post("/set-openai-key")
def set_openai_key_endpoint(request: SetKeyRequest) -> dict[str, str | bool]:
    """Store/replace the per-user OpenAI API key securely.

    The implementation handles encryption of the API key before storage.
    This endpoint satisfies the OAuth/credentials requirement by allowing
    users to securely provide their OpenAI API credentials.

    Args:
        request: Contains subject (user ID) and OpenAI API key

    Returns:
        Success confirmation with subject

    Raises:
        HTTPException: If API key storage fails

    """
    try:
        set_openai_key(request.subject, request.api_key)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store API key: {e!s}",
        ) from e
    else:
        return {
            "ok": True,
            "subject": request.subject,
            "message": "OpenAI API key stored securely",
        }
