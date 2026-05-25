"""Tracing abstraction for LangSmith, Phoenix, or OpenTelemetry exporters."""

from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelemetryClient:
    """Minimal tracing facade used by orchestration code."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    @contextmanager
    def trace(self, name: str, **attributes: object) -> Iterator[None]:
        """Create a lightweight trace span placeholder."""
        logger.debug("trace_start", extra={"trace_name": name, "provider": self.provider, "attributes": attributes})
        try:
            yield
        finally:
            logger.debug("trace_end", extra={"trace_name": name, "provider": self.provider})


def get_telemetry_client() -> TelemetryClient:
    """Return the configured telemetry client facade."""
    settings = get_settings()
    return TelemetryClient(provider=settings.tracing_provider)
