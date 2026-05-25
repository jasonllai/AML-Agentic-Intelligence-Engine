"""Redis client factory."""

from redis import Redis

from app.core.config import get_settings


def get_redis_client() -> Redis:
    """Return a Redis client configured from environment variables."""
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)

