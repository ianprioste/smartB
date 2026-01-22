"""Redis client configuration."""
import redis
from app.settings import settings


def get_redis_client():
    """Get Redis client instance."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


redis_client = get_redis_client()
