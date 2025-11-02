"""AI Service Adapter.

This package provides an adapter that exposes a small, stable API for
consumers and forwards calls to the OpenAI Client Service using explicit HTTP
calls. The implementation is intentionally minimal and mirrors the HW1 style.
"""

from ._adapter import AdapterAPIError, AdapterError, AdapterNetworkError, OpenAIServiceAdapter

__all__ = ["AdapterAPIError", "AdapterError", "AdapterNetworkError", "OpenAIServiceAdapter"]
