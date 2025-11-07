"""FastAPI application for OpenAI Client Service."""

from dotenv import load_dotenv
from fastapi import FastAPI

try:  # pragma: no cover - optional dependency for tests without crypto/openai
    from openai_client_impl import init_db  # type: ignore[attr-defined]
except Exception:  # pragma: no cover  # noqa: BLE001
    def init_db() -> None:
        """No-op init when optional dependencies are unavailable."""
        return

from .routes import ai, oauth

load_dotenv()

app = FastAPI(
    title="OpenAI Client Service",
    description="A service for managing OpenAI API interactions with secure credential storage",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Initialize database on application startup."""
    init_db()


app.include_router(oauth.router, prefix="/auth", tags=["Authentication"])
app.include_router(ai.router, prefix="/ai", tags=["AI Operations"])


@app.get("/health")  # type: ignore[misc]
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    # Keep the response minimal to satisfy integration tests that expect exactly
    # {"status": "ok"}.
    return {"status": "ok"}
