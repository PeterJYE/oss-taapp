"""Public API for the openai_client_impl package."""

from .client import OpenAIClientImpl
from .storage import init_db, set_openai_key, get_openai_key
from .errors import MissingOpenAIKeyError

__all__ = [
    "OpenAIClientImpl",
    "init_db",
    "set_openai_key",
    "get_openai_key",
    "MissingOpenAIKeyError",
]

__version__ = "0.1.0"