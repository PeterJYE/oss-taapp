from fastapi import APIRouter

router = APIRouter()


@router.get("/channels", tags=["channels"])
def list_channels() -> list[dict[str, str]]:
    # Minimal in-memory data to satisfy tests and adapter sanity
    return [
        {"id": "C001", "name": "general"},
        {"id": "C002", "name": "random"},
    ]
