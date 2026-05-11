from redis.asyncio import Redis

from app.config import settings


redis_client: Redis | None = None


async def connect_to_redis() -> None:
    global redis_client
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis_client.ping()


async def close_redis_connection() -> None:
    if redis_client:
        await redis_client.aclose()


def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis connection has not been initialized")
    return redis_client


def unread_key(user_id: str, conversation_id: str) -> str:
    return f"chat:unread:{user_id}:{conversation_id}"


def presence_key(user_id: str) -> str:
    return f"chat:presence:{user_id}"


def conversation_cache_key(conversation_id: str) -> str:
    return f"chat:conversation:{conversation_id}"
