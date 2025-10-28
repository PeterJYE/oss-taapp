from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI
from .storage import get_openai_key
from .errors import MissingOpenAIKeyError

DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
DEFAULT_EMBED_MODEL = os.getenv("OPENAI_DEFAULT_EMBED", "text-embedding-3-small")

class OpenAIClientImpl:
    """Concrete impl using a per-user OpenAI API key stored securely."""

    def _sdk(self, subject: str) -> OpenAI:
        key = get_openai_key(subject)
        if not key:
            raise MissingOpenAIKeyError(
                "OpenAI API key is not set for this user. Set it via the service."
            )
        return OpenAI(api_key=key)

    def chat(
        self, *, subject: str, messages: List[Dict[str, Any]], model: Optional[str] = None
    ) -> Dict[str, Any]:
        client = self._sdk(subject)
        m = model or DEFAULT_MODEL
        resp = client.chat.completions.create(model=m, messages=messages)
        return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    def embed(
        self, *, subject: str, inputs: List[str], model: Optional[str] = None
    ) -> Dict[str, Any]:
        client = self._sdk(subject)
        m = model or DEFAULT_EMBED_MODEL
        resp = client.embeddings.create(model=m, input=inputs)
        return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
