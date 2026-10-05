"""Fixed-window per-IP rate limiting on top of the shared cache.

Fixed windows allow a burst of up to 2x the limit across a window boundary;
that's an acceptable trade for one cache round-trip per request. The client
IP comes from request.client, which uvicorn fills from X-Forwarded-For when
run with --proxy-headers (see backend/start.sh).
"""

import time

from fastapi import HTTPException, Request

from app.core.cache import get_cache
from app.core.config import get_settings

_PERIODS = {"second": 1, "minute": 60, "hour": 3600}


def parse_rate(rate: str) -> tuple[int, int]:
    count, _, period = rate.partition("/")
    if period not in _PERIODS:
        raise ValueError(f"Bad rate limit {rate!r}; expected '<n>/<second|minute|hour>'.")
    return int(count), _PERIODS[period]


def rate_limit(scope: str):
    """FastAPI dependency factory: Depends(rate_limit("analyze")) enforces
    settings.rate_limit_analyze. Read per request so config changes apply."""
    parse_rate(getattr(get_settings(), f"rate_limit_{scope}"))  # fail fast on a typo

    async def dependency(request: Request) -> None:
        limit, window = parse_rate(getattr(get_settings(), f"rate_limit_{scope}"))
        client_ip = request.client.host if request.client else "unknown"
        window_start = int(time.time()) // window
        key = f"rl:{scope}:{client_ip}:{window_start}"
        count = await get_cache().incr(key, ttl_seconds=window)
        if count > limit:
            retry_after = window - int(time.time()) % window
            raise HTTPException(
                status_code=429,
                detail="Too many requests — please slow down and try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
