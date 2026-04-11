"""Redis client configuration."""
import logging
from app.settings import settings

_logger = logging.getLogger(__name__)


def get_redis_client():
    """Get Redis client instance. Returns None when Redis is unavailable."""
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        _logger.warning("Redis unavailable (%s) – running without cache/celery.", exc)
        return None


redis_client = get_redis_client()
