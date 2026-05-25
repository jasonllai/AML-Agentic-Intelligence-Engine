"""FastAPI application entrypoint for the AML Agentic Intelligence Workbench."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analysis, health, reports, roles
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure process-wide services for the API lifecycle."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting AML Agentic Intelligence Workbench", extra={"environment": settings.environment})
    yield
    logger.info("Stopping AML Agentic Intelligence Workbench")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Role-aware AML multi-agent intelligence API foundation.",
        lifespan=lifespan,
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(roles.router, prefix=settings.api_prefix)
    app.include_router(analysis.router, prefix=settings.api_prefix)
    app.include_router(reports.router, prefix=settings.api_prefix)
    return app


app = create_app()

