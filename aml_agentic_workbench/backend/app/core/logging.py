"""Logging setup with OpenTelemetry-friendly structured fields."""

import logging
import sys
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for local and container execution."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    return logging.getLogger(name)


def otel_attributes(**attributes: Any) -> dict[str, Any]:
    """Build structured attributes compatible with OpenTelemetry log processors."""
    return {"otel_attributes": attributes}

