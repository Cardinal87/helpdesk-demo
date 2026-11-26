"""Redis infrastructure: FSM storage and a plain async client.

aiogram 3.x ships RedisStorage; we configure it with short key TTLs so stale
FSM states disappear together with role sessions. The same client is reused
for throttling counters and the workspace-TTL background sweep lock.
"""

from __future__ import annotations

from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import ConnectionPool, Redis

from app.config import Settings


def build_redis(settings: Settings) -> Redis:
    pool = ConnectionPool.from_url(settings.redis_url, max_connections=16)
    return Redis(connection_pool=pool)


def build_fsm_storage(redis_client: Redis) -> RedisStorage:
    # Key TTL slightly above role session TTL; state data is cheap and disposable.
    return RedisStorage(redis=redis_client)
