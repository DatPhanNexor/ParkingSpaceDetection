import os
import redis.asyncio as redis
from contextlib import asynccontextmanager

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def get_redis():
    return redis_client

@asynccontextmanager
async def acquire_lock(lock_key: str, timeout: int = 10):
    """
    Simple distributed lock using SET NX PX
    """
    lock_value = os.urandom(8).hex()
    acquired = await redis_client.set(lock_key, lock_value, nx=True, px=timeout*1000)
    try:
        yield acquired
    finally:
        if acquired:
            # Only release if we still own it
            current = await redis_client.get(lock_key)
            if current == lock_value:
                await redis_client.delete(lock_key)
