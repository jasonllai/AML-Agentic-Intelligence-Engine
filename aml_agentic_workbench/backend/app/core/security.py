"""Security utilities and placeholders for future auth integration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """Authenticated user context for audit and authorization decisions."""

    subject: str
    roles: tuple[str, ...]


def get_system_principal() -> Principal:
    """Return a system principal for unauthenticated local development routes."""
    return Principal(subject="system", roles=("service",))

