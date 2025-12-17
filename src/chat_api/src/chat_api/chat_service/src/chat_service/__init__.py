from __future__ import annotations

# Re-export FastAPI app for uvicorn convenience, e.g.:
# uvicorn chat_service.app:app --reload
from .app import app  # noqa: F401
