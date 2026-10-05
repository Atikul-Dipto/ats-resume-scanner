import asyncio
from datetime import UTC, datetime, timedelta

import fakeredis
import jwt
import pytest

from app.core.cache import MemoryCache, RedisCache
from app.core.config import DEV_JWT_SECRET, Settings, get_settings
from app.core.rate_limit import parse_rate
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def run(coro):
    return asyncio.run(coro)


def test_password_hash_roundtrip_and_salting():
    first = hash_password("s3cret-password")
    second = hash_password("s3cret-password")
    assert first != second  # unique salt per hash
    assert verify_password("s3cret-password", first)
    assert not verify_password("wrong-password", first)


def test_verify_password_rejects_malformed_hashes():
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "bcrypt$1$2$3$abc$def")


def test_access_token_roundtrip():
    assert decode_access_token(create_access_token("user-123")) == "user-123"


def test_expired_and_tampered_tokens_are_rejected():
    secret = get_settings().jwt_secret
    expired = jwt.encode(
        {"sub": "user-123", "exp": datetime.now(UTC) - timedelta(minutes=1)}, secret, algorithm="HS256"
    )
    assert decode_access_token(expired) is None
    forged = jwt.encode({"sub": "user-123"}, "some-other-secret-that-is-long-enough-for-hs256", algorithm="HS256")
    assert decode_access_token(forged) is None
    assert decode_access_token("garbage") is None


def test_postgres_urls_are_rewritten_to_psycopg3_driver():
    assert Settings(database_url="postgres://u:p@h/db").sqlalchemy_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql://u:p@h/db?sslmode=require").sqlalchemy_url == (
        "postgresql+psycopg://u:p@h/db?sslmode=require"
    )
    assert Settings(database_url="sqlite:///x.db").sqlalchemy_url == "sqlite:///x.db"


def test_production_refuses_default_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(ValueError, match="32"):
        Settings(environment="production", jwt_secret="too-short")
    Settings(environment="production", jwt_secret="x" * 32)


def test_parse_rate():
    assert parse_rate("12/minute") == (12, 60)
    assert parse_rate("5/second") == (5, 1)
    with pytest.raises(ValueError):
        parse_rate("5/fortnight")


def test_memory_cache_get_set_expiry(monkeypatch):
    cache = MemoryCache()
    now = [1000.0]
    monkeypatch.setattr("app.core.cache.time.monotonic", lambda: now[0])

    run(cache.set("k", {"a": 1}, ttl_seconds=10))
    assert run(cache.get("k")) == {"a": 1}
    now[0] += 11
    assert run(cache.get("k")) is None


def test_memory_cache_incr_keeps_original_expiry(monkeypatch):
    cache = MemoryCache()
    now = [0.0]
    monkeypatch.setattr("app.core.cache.time.monotonic", lambda: now[0])

    assert run(cache.incr("n", 60)) == 1
    now[0] += 30
    assert run(cache.incr("n", 60)) == 2
    now[0] += 31  # past the first increment's window
    assert run(cache.incr("n", 60)) == 1


def test_memory_cache_is_bounded():
    cache = MemoryCache(max_entries=3)
    for i in range(10):
        run(cache.set(f"k{i}", i, 60))
    assert len(cache._data) <= 3
    assert run(cache.get("k9")) == 9


def test_redis_cache_backend():
    cache = RedisCache(fakeredis.FakeAsyncRedis(decode_responses=True))

    async def scenario():
        await cache.set("k", [1, 2, 3], 60)
        assert await cache.get("k") == [1, 2, 3]
        assert await cache.get("missing") is None
        assert await cache.incr("counter", 60) == 1
        assert await cache.incr("counter", 60) == 2
        assert await cache.ping()

    run(scenario())
