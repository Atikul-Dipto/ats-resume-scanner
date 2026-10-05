from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.cache import get_cache
from app.core.config import get_settings
from app.db.session import get_engine
from app.matching.store import event_count, resume_scan_count

router = APIRouter(prefix="/api", tags=["ops"])

STATS_TTL_SECONDS = 60


@router.get("/health")
async def health():
    """Liveness: the process is up. Deliberately touches no dependencies, so a
    database blip doesn't make the platform restart a healthy container."""
    return {"status": "ok"}


def _db_ok() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/meta")
async def meta():
    """Deployment facts the UI needs to be honest with users."""
    settings = get_settings()
    return {
        "persistent_storage": settings.persistent_storage,
        "admin_configured": bool(settings.admin_emails_set),
    }


@router.get("/ready")
async def ready():
    """Readiness: dependencies are reachable. Point a load balancer here."""
    checks = {"database": await run_in_threadpool(_db_ok), "cache": await get_cache().ping()}
    healthy = all(checks.values())
    return JSONResponse({"status": "ok" if healthy else "degraded", "checks": checks},
                        status_code=200 if healthy else 503)


@router.get("/stats")
async def stats():
    """Aggregate counts only — no per-scan or per-search detail exposed here.
    Cached briefly so a public endpoint can't drive COUNT(*) queries at will."""
    cache = get_cache()
    cached = await cache.get("stats:v1")
    if cached is not None:
        return cached
    payload = {
        "resume_scans": await run_in_threadpool(resume_scan_count),
        "job_search_events": await run_in_threadpool(event_count),
    }
    await cache.set("stats:v1", payload, STATS_TTL_SECONDS)
    return payload
