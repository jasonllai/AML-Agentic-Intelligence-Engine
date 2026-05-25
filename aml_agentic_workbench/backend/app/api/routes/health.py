"""Health and readiness endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Basic API health response."""

    status: str
    service: str
    version: str
    timestamp: datetime


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return API liveness information."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(UTC),
    )

