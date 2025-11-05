"""AI Service adapter package exports.

Re-exports the public adapter API for test and consumer imports.
"""

from ._adapter import AdapterAPIError, AdapterError, OpenAIServiceAdapter

__all__ = [
    "AdapterAPIError",
    "AdapterError",
    "OpenAIServiceAdapter",
]
