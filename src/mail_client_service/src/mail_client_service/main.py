"""FastAPI service for the mail client API.

This module provides a REST API wrapper around the mail_client_api abstraction,
allowing clients to interact with mail services via HTTP endpoints.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel

import mail_client_api

logger = logging.getLogger("mail_client_service")
logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="Mail Client Service",
    version="1.0.0",
    description="Thin FastAPI wrapper around mail_client_api.get_client()",
)


def get_client_dep() -> mail_client_api.Client:
    """Dependency that retrieves a mail client instance using the existing factory.

    Keep behavior simple for tests: return the client or propagate the original error.
    """
    # Use positional arg for tests that stub get_client without keyword name
    return mail_client_api.get_client(True)  # noqa: FBT003


class MessageSummary(BaseModel):
    """A summary of a message containing only essential information."""

    id: str
    subject: str | None = None


class MessageDetail(BaseModel):
    """Complete message details."""

    id: str
    from_: str
    to: str
    date: str
    subject: str
    body: str


class ActionResult(BaseModel):
    """Response indicating whether an action succeeded."""

    ok: bool
    message: str | None = None


@app.get("/messages", response_model=list[MessageSummary])
def list_messages(
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of messages to fetch")] = 10,
    client: Annotated[mail_client_api.Client, Depends(get_client_dep)] = None,
) -> list[MessageSummary]:
    """Fetch a list of message summaries. Uses client.get_messages() and returns id + subject."""
    try:
        messages_iter = client.get_messages(max_results=limit)
    except Exception as e:
        logger.exception("Failed to fetch messages")
        raise HTTPException(status_code=500, detail="Failed to fetch messages") from e

    summaries: list[MessageSummary] = []
    try:
        for msg in messages_iter:
            item: MessageSummary = {
                "id": msg.id,
            }
            if msg.subject:
                item["subject"] = msg.subject
            summaries.append(item)
    except Exception as e:
        logger.exception("Error iterating messages")
        raise HTTPException(status_code=500, detail="Error processing messages") from e

    return summaries


@app.get("/messages/{message_id}", response_model=MessageDetail)
def get_message_detail(
    message_id: str,
    client: Annotated[mail_client_api.Client, Depends(get_client_dep)] = None,
) -> MessageDetail:
    """Fetch the full detail of a single message via client.get_message().

    Returns the complete message information including sender, recipient, subject, body, and date.
    """
    try:
        msg = client.get_message(message_id)
    except Exception as e:
        logger.exception("Failed to fetch message %s", message_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message '{message_id}' not found or could not be retrieved.",
        ) from e

    return MessageDetail(
        id=msg.id,
        from_=msg.from_,
        to=msg.to,
        date=msg.date,
        subject=msg.subject,
        body=msg.body,
    )


@app.post("/messages/{message_id}/mark-as-read", response_model=ActionResult, status_code=status.HTTP_200_OK)
def mark_message_as_read(
    message_id: str,
    client: Annotated[mail_client_api.Client, Depends(get_client_dep)] = None,
) -> ActionResult:
    """Mark a message as read via client.mark_as_read()."""
    try:
        ok: bool = client.mark_as_read(message_id)
    except Exception as e:
        logger.exception("Error marking message %s as read", message_id)
        raise HTTPException(status_code=500, detail="Failed to mark message as read") from e

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not mark message '{message_id}' as read.",
        )
    return ActionResult(ok=True, message=f"Message '{message_id}' marked as read")


@app.delete("/messages/{message_id}", response_model=ActionResult, status_code=status.HTTP_200_OK)
def delete_message(
    message_id: str,
    client: Annotated[mail_client_api.Client, Depends(get_client_dep)] = None,
) -> ActionResult:
    """Permanently delete a message via client.delete_message().

    This operation cannot be undone.
    """
    try:
        ok: bool = client.delete_message(message_id)
    except Exception as e:
        logger.exception("Error deleting message %s", message_id)
        raise HTTPException(status_code=500, detail="Failed to delete message") from e

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not delete message '{message_id}'.",
        )
    return ActionResult(ok=True, message=f"Message '{message_id}' deleted successfully")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mail_client_service.main:app", host="127.0.0.1", port=8000, reload=True)
