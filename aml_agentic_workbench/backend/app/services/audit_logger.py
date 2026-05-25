"""Audit logging service abstraction."""

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AuditEvent:
    """Structured audit event emitted by routes and agents."""

    actor: str
    action: str
    target: str
    metadata: dict[str, Any]


class AuditLogger:
    """Audit sink facade that can later persist to PostgreSQL and SIEM tooling."""

    def log(self, event: AuditEvent) -> None:
        """Emit an audit event through the configured logger."""
        logger.info(
            "audit_event",
            extra={
                "actor": event.actor,
                "action": event.action,
                "target": event.target,
                "metadata": event.metadata,
            },
        )

