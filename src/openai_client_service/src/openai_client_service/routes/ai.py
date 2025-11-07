"""AI operation routes for OpenAI Client Service."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from openai_service_api.client import AIClient
from pydantic import BaseModel

try:  # pragma: no cover - optional dependency for environments without openai/crypto
    from openai_client_impl import MissingOpenAIKeyError  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - define a fallback exception type  # noqa: BLE001
    class MissingOpenAIKeyError(Exception):
        """Fallback error used when openai_client_impl is unavailable."""

from openai_client_service.dependencies import get_ai_client

router = APIRouter()


class GenerateResponseRequest(BaseModel):  # type: ignore[misc]
    """Request model for generate response endpoint."""

    messages: list[str]
    conversation_id: str | None = None


@router.post("/generate-response")  # type: ignore[misc]
def generate_response(
    request: GenerateResponseRequest,
    aiclient: Annotated[AIClient, Depends(get_ai_client)],
) -> dict[str, str | int | None]:
    """Generate a model response using the abstract AIClient interface.

    This endpoint uses the AIClient interface to generate responses and manage
    conversation history, providing the core functionality for AI interactions.

    Args:
        request: Generate response request with messages and optional conversation ID
        aiclient: AI client instance for the authenticated user (injected via dependency)

    Returns:
        Response with content, tokens_used, and conversation_id

    Raises:
        HTTPException: If OpenAI API key is not set or request is invalid

    """
    try:
        response = aiclient.generate_response(request.messages, conversation_id=request.conversation_id)
    except Exception as e:
        # Accept both real MissingOpenAIKeyError and fallback class from dependencies module
        if "OpenAI API key" in str(e):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "OpenAI API key is not set",
                    "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
                },
            )
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {
            "content": response.content,
            "tokens_used": response.tokens_used,
            "conversation_id": response.conversation_id,
        }


class CreateConversationRequest(BaseModel):  # type: ignore[misc]
    """Empty request model so OpenAPI includes a requestBody."""



@router.post("/conversations")  # type: ignore[misc]
def create_conversation(
    aiclient: Annotated[AIClient, Depends(get_ai_client)],
    _payload: CreateConversationRequest | None = None,
) -> dict[str, str]:
    """Create a new conversation and return its ID.

    Args:
        aiclient: AI client instance for the authenticated user (injected via dependency)

    Returns:
        Conversation ID for the newly created conversation

    Raises:
        HTTPException: If conversation creation fails

    """
    try:
        conv_id = aiclient.create_conversation()
    except MissingOpenAIKeyError:
        return JSONResponse(
            status_code=401,
            content={
                "error": "OpenAI API key is not set",
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {"conversation_id": conv_id}


@router.get("/conversations/{conversation_id}")  # type: ignore[misc]
def get_conversation(
    conversation_id: str,
    aiclient: Annotated[AIClient, Depends(get_ai_client)],
) -> dict[str, str | list[tuple[str, str]]]:
    """Retrieve a conversation by its ID.

    Args:
        conversation_id: The unique identifier of the conversation
        aiclient: AI client instance for the authenticated user (injected via dependency)

    Returns:
        Conversation object with messages and metadata

    Raises:
        HTTPException: If conversation is not found

    """
    try:
        conversation = aiclient.get_conversation(conversation_id)
    except MissingOpenAIKeyError:
        return JSONResponse(
            status_code=401,
            content={
                "error": "OpenAI API key is not set",
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        return {
            "id": conversation.id,
            "messages": conversation.messages,
            "created_at": conversation.created_at,
        }


@router.delete("/conversations/{conversation_id}")  # type: ignore[misc]
def delete_conversation(
    conversation_id: str,
    aiclient: Annotated[AIClient, Depends(get_ai_client)],
) -> dict[str, str | bool]:
    """Delete a conversation and all its messages.

    Args:
        conversation_id: The unique identifier of the conversation
        aiclient: AI client instance for the authenticated user (injected via dependency)

    Returns:
        Success status

    Raises:
        HTTPException: If deletion fails

    """
    try:
        success = aiclient.delete_conversation(conversation_id)
    except MissingOpenAIKeyError:
        return JSONResponse(
            status_code=401,
            content={
                "error": "OpenAI API key is not set",
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        if success:
            return {"ok": True, "conversation_id": conversation_id, "message": "Conversation deleted"}
        return {"ok": False, "message": "Conversation not found"}
