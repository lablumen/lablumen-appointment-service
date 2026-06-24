import redis.asyncio as redis

from .config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def acquire_slot_lock(slot_key: str, ttl: int | None = None) -> bool:
    """Best-effort distributed lock for an appointment slot.

    Returns True if this worker acquired the slot, False if another worker holds it.
    Lock auto-expires after ``ttl`` seconds (default: settings.slot_lock_ttl_seconds).
    """
    ttl = ttl or settings.slot_lock_ttl_seconds
    acquired = await redis_client.set(f"slot-lock:{slot_key}", "1", nx=True, ex=ttl)
    return bool(acquired)


async def release_slot_lock(slot_key: str) -> None:
    await redis_client.delete(f"slot-lock:{slot_key}")
