from time import time
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PostMessage(BaseModel):
    channel_id: str
    text: str


@router.post("/messages", tags=["messages"])
def post_message(payload: PostMessage) -> dict[str, str]:
    # Generate a Slack-like ts and a unique id for the message
    ts = f"{int(time())}.000001"
    message_id = f"msg_{uuid4().hex}"
    return {
        "id": message_id,
        "channel_id": payload.channel_id,
        "text": payload.text,
        "ts": ts,
    }
