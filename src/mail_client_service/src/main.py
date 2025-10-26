# mail_client_service/main.py

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel

import gmail_client_impl  # Automatically registers with mail_client_api
import mail_client_api


logger = logging.getLogger("mail_client_service")
logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="Mail Client Service",
    version="1.0.0",
    description="Thin FastAPI wrapper around mail_client_api.get_client()",
)


def get_client_dep():
    """
    Dependency that retrieves a mail client instance using the existing factory.
    No auth/logic is re-implemented here.
    """
    import os
    # Change to the project root directory where credentials.json is located
    original_cwd = os.getcwd()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    os.chdir(project_root)
    
    try:
        # Enable interactive mode for easier authentication during development
        client = mail_client_api.get_client(interactive=True)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to initialize mail client via factory: %s", e)
        os.chdir(original_cwd)  # Restore original working directory
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize mail client",
        ) from e
    finally:
        os.chdir(original_cwd)  # Always restore original working directory
    
    return client


class MessageSummary(BaseModel):
    """A summary of a message containing only essential information."""
    id: str
    subject: Optional[str] = None


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
    message: Optional[str] = None


@app.get("/messages", response_model=List[MessageSummary])
def list_messages(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of messages to fetch"),
    client=Depends(get_client_dep),
):
    """
    Fetch a list of message summaries. Uses client.get_messages() and returns id + subject.
    """
    try:
        messages_iter = client.get_messages(max_results=limit)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to fetch messages: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch messages") from e

    summaries: List[MessageSummary] = []
    try:
        for msg in messages_iter:
            # Use the Message contract properties
            item: MessageSummary = {
                "id": msg.id,
            }
            if msg.subject:
                item["subject"] = msg.subject
            summaries.append(item)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error iterating messages: %s", e)
        raise HTTPException(status_code=500, detail="Error processing messages") from e

    return summaries


@app.get("/messages/{message_id}", response_model=MessageDetail)
def get_message_detail(message_id: str, client=Depends(get_client_dep)):
    """
    Fetch the full detail of a single message via client.get_message().
    Returns the complete message information including sender, recipient, subject, body, and date.
    """
    try:
        msg = client.get_message(message_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to fetch message %s: %s", message_id, e)
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
def mark_message_as_read(message_id: str, client=Depends(get_client_dep)):
    """
    Mark a message as read via client.mark_as_read().
    """
    try:
        ok: bool = client.mark_as_read(message_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error marking message %s as read: %s", message_id, e)
        raise HTTPException(status_code=500, detail="Failed to mark message as read") from e

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not mark message '{message_id}' as read.",
        )
    return ActionResult(ok=True, message=f"Message '{message_id}' marked as read")


@app.delete("/messages/{message_id}", response_model=ActionResult, status_code=status.HTTP_200_OK)
def delete_message(message_id: str, client=Depends(get_client_dep)):
    """
    Permanently delete a message via client.delete_message().
    This operation cannot be undone.
    """
    try:
        ok: bool = client.delete_message(message_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error deleting message %s: %s", message_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete message") from e

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not delete message '{message_id}'.",
        )
    return ActionResult(ok=True, message=f"Message '{message_id}' deleted successfully")


# Optional: local dev server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mail_client_service.main:app", host="0.0.0.0", port=8000, reload=True)
