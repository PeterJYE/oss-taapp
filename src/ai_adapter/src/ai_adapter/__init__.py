"""AI Service Adapter.

This package provides an adapter that exposes a small, stable API for
consumers and forwards calls to a remote AI service (via an auto-generated
client or an HTTP ``base_url``). The implementation is intentionally minimal
and designed to be wired into the HW2 pipeline as the Service Client Adapter.
"""

from ._adapter import AdapterAPIError, AdapterError, AIAdapter

__all__ = ["AIAdapter", "AdapterAPIError", "AdapterError"]
