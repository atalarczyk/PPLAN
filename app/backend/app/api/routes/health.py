"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Simple liveness endpoint."""

    return {"status": "ok"}

