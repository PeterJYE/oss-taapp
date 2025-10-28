from fastapi import APIRouter, Form
from openai_client_impl import set_openai_key  # from your impl

router = APIRouter()

@router.post("/set-openai-key")
def set_openai_key_endpoint(subject: str = Form(...), api_key: str = Form(...)):
    """
    Store/replace the per-user OpenAI API key securely (impl handles encryption).
    This is the simplest way to “finish the OAuth/credentials” requirement for HW:
    the service exposes an endpoint to provide credentials to the impl.
    """
    set_openai_key(subject, api_key)
    return {"ok": True, "subject": subject}
