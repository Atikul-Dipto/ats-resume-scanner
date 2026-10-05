"""Small async key/value cache with two interchangeable backends.

- MemoryCache: per-process. Correct for a single API instance (the free tier).
- RedisCache: shared. Required once there is more than one instance, so job
  search results and rate-limit counters are shared instead of per-process.

The backend is picked from settings.redis_url; nothing else in the app knows
which one it's talking to. Values must be JSON-serializable.
"""

import json
import time
from typing import Any, Protocol

from app.core.config import get_settings


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    async def incr(self, key: str, ttl_seconds: int) -> int: ...
    async def ping(self) -> bool: ...


class MemoryCache:
    """Expiring dict. Bounded so a flood of distinct keys can't grow it forever."""

    def __init__(self, max_entries: int = 10_000):
        self._data: dict[str, tuple[float, Any]] = {}
        self._max_entries = max_entries

    def _evict(self) -> None:
        now = time.monotonic()
        for key in [k for k, (exp, _) in self._data.items() if exp <= now]:
            del self._data[key]
        while len(self._data) >= self._max_entries:
            # Dicts keep insertion order, so this drops the oldest entry.
            del self._data[next(iter(self._data))]

    async def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if key not in self._data and len(self._data) >= self._max_entries:
            self._evict()
        self._data[key] = (time.monotonic() + ttl_seconds, value)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        current = await self.get(key)
        if current is None:
            await self.set(key, 1, ttl_seconds)
            return 1
        expires_at, _ = self._data[key]
        self._data[key] = (expires_at, current + 1)
        return current + 1

    async def ping(self) -> bool:
        return True


class RedisCache:
    def __init__(self, client):
        self._client = client

    @classmethod
    def from_url(cls, url: str) -> "RedisCache":
        import redis.asyncio as redis

        return cls(redis.from_url(url, decode_responses=True))

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self._client.set(key, json.dumps(value), ex=ttl_seconds)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl_seconds, nx=True)
            count, _ = await pipe.execute()
        return int(count)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        url = get_settings().redis_url
        _cache = RedisCache.from_url(url) if url else MemoryCache()
    return _cache


def set_cache(cache: Cache | None) -> None:
    """Swap the backend (tests use this to reset state between cases)."""
    global _cache
    _cache = cache
