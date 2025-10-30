"""AI operation routes for OpenAI Client Service."""


from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from openai_client_impl import AIClientImpl, MissingOpenAIKeyError
from openai_client_service.dependencies import get_authenticated_subject

router = APIRouter()


class GenerateResponseRequest(BaseModel):
    """Request model for generate response endpoint."""

    messages: list[str]
    conversation_id: str | None = None


@router.post("/generate-response")
def generate_response(
    request: GenerateResponseRequest,
    subject: Annotated[str, Depends(get_authenticated_subject)],
) -> dict[str, str | int | None]:
    """Generate a model response using the abstract AIClient interface.

    This endpoint uses the AIClient interface to generate responses and manage
    conversation history, providing the core functionality for AI interactions.

    Args:
        request: Generate response request with messages and optional conversation ID
        subject: User subject from OAuth session

    Returns:
        Response with content, tokens_used, and conversation_id

    Raises:
        HTTPException: If OpenAI API key is not set or request is invalid

    """
    try:
        aiclient = AIClientImpl(subject=subject)
        response = aiclient.generate_response(request.messages, conversation_id=request.conversation_id)
    except MissingOpenAIKeyError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        ) from e
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


@router.post("/conversations")
def create_conversation(subject: Annotated[str, Depends(get_authenticated_subject)]) -> dict[str, str]:
    """Create a new conversation and return its ID.

    Returns:
        Conversation ID for the newly created conversation

    Raises:
        HTTPException: If conversation creation fails

    """
    try:
        aiclient = AIClientImpl(subject=subject)
        conv_id = aiclient.create_conversation()
    except MissingOpenAIKeyError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {"conversation_id": conv_id}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, subject: Annotated[str, Depends(get_authenticated_subject)],
) -> dict[str, str | list[tuple[str, str]]]:
    """Retrieve a conversation by its ID.

    Args:
        conversation_id: The unique identifier of the conversation
        subject: User subject from OAuth session

    Returns:
        Conversation object with messages and metadata

    Raises:
        HTTPException: If conversation is not found

    """
    try:
        aiclient = AIClientImpl(subject=subject)
        conversation = aiclient.get_conversation(conversation_id)
    except MissingOpenAIKeyError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        return {
            "id": conversation.id,
            "messages": conversation.messages,
            "created_at": conversation.created_at,
        }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, subject: Annotated[str, Depends(get_authenticated_subject)]) -> dict[str, str | bool]:
    """Delete a conversation and all its messages.

    Args:
        conversation_id: The unique identifier of the conversation
        subject: User subject from OAuth session

    Returns:
        Success status

    Raises:
        HTTPException: If deletion fails

    """
    try:
        aiclient = AIClientImpl(subject=subject)
        success = aiclient.delete_conversation(conversation_id)
    except MissingOpenAIKeyError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": str(e),
                "hint": "POST /auth/set-openai-key first to set your OpenAI API key.",
            },
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        if success:
            return {"ok": True, "conversation_id": conversation_id, "message": "Conversation deleted"}
        return {"ok": False, "message": "Conversation not found"}
