from fastapi import APIRouter, Body, Depends
from openai_client_impl import OpenAIClientImpl, MissingOpenAIKeyError
from ..dependencies import get_subject

router = APIRouter()
client = OpenAIClientImpl()

@router.post("/chat")
def chat(
    payload: dict = Body(...),
    subject: str = Depends(get_subject),
):
    """
    Body example:
    {
      "messages": [{"role":"user","content":"Say hi!"}],
      "model": "gpt-4o-mini"
    }
    """
    messages = payload.get("messages", [])
    model = payload.get("model")
    try:
        return client.chat(subject=subject, messages=messages, model=model)
    except MissingOpenAIKeyError as e:
        return {"error": str(e), "hint": "POST /auth/set-openai-key first."}

@router.post("/embed")
def embed(
    payload: dict = Body(...),
    subject: str = Depends(get_subject),
):
    """
    Body example:
    {
      "input": ["hello", "world"],
      "model": "text-embedding-3-small"
    }
    """
    inputs = payload.get("input", [])
    model = payload.get("model")
    try:
        return client.embed(subject=subject, inputs=inputs, model=model)
    except MissingOpenAIKeyError as e:
        return {"error": str(e), "hint": "POST /auth/set-openai-key first."}
