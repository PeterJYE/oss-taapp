"""Public API for the openai_client_impl package."""

from .ai_client import AIClientImpl
from .errors import MissingOpenAIKeyError
from .response import Conversation, Response, get_conversation, get_response
from .storage import get_openai_key, init_db, set_openai_key

__all__ = [
    "AIClientImpl",
    "Conversation",
    "MissingOpenAIKeyError",
    "Response",
    "get_conversation",
    "get_openai_key",
    "get_response",
    "init_db",
    "set_openai_key",
]

__version__ = "0.1.0"
