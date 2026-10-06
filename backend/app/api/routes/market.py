"""Work Signal: job-market signals computed from the open-jobs catalog."""

import httpx
from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from app.core.cache import get_cache
from app.db.session import get_session_factory
from app.jobs.indicators import fetch_indicators
from app.jobs.market import compute_market
from app.schemas.jobs import Discipline, Workplace

router = APIRouter(prefix="/api/market", tags=["market"])

MARKET_TTL_SECONDS = 300
INDICATORS_TTL_SECONDS = 24 * 3600  # published yearly; one fetch a day is plenty
INDICATORS_RETRY_SECONDS = 600


def market_snapshot(discipline=None, workplace=None) -> dict:
    with get_session_factory()() as db:
        return jsonable_encoder(compute_market(db, discipline=discipline, workplace=workplace))


@router.get("")
async def market(discipline: Discipline | None = None, workplace: Workplace | None = None):
    """Cached for a few minutes: one public request shouldn't scan the catalog every time."""
    key = f"market:v1:{discipline or '-'}:{workplace or '-'}"
    cache = get_cache()
    cached = await cache.get(key)
    if cached is not None:
        return cached
    payload = await run_in_threadpool(market_snapshot, discipline, workplace)
    await cache.set(key, payload, MARKET_TTL_SECONDS)
    return payload


@router.get("/indicators")
async def indicators(request: Request):
    """Official Bangladesh labour statistics (World Bank WDI), cached for a day.
    A failed fetch is cached briefly too, so an outage isn't retried per request."""
    cache = get_cache()
    cached = await cache.get("market:indicators:v1")
    if cached is not None:
        return cached
    client = getattr(request.app.state, "http", None)
    if client is None:
        async with httpx.AsyncClient() as own:
            data = await fetch_indicators(own)
    else:
        data = await fetch_indicators(client)
    await cache.set("market:indicators:v1", data, INDICATORS_TTL_SECONDS if data["available"] else INDICATORS_RETRY_SECONDS)
    return data
