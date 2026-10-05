"""Pulls remote engineering/data jobs from the public job APIs into the catalog.

Runs (a) in the background when the catalog is read and the last sync is
older than JOBS_SYNC_INTERVAL_HOURS, (b) on demand from the admin API, or
(c) from a scheduler: `python -m app.jobs.sync` (cron / GitHub Actions at scale).

Rules:
- Only remote roles that classify into a supported discipline are kept:
  an on-site job in Berlin is noise for a candidate in Dhaka. Local on-site
  roles come from admin-posted listings instead.
- Upsert by (source, url); an admin who hid an imported job keeps it hidden.
- APIs return only their top results, so a job missing from one sync isn't
  closed — it ages out after JOBS_EXTERNAL_MAX_AGE_DAYS without being seen.
"""

import asyncio
import html
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, func, select

from app.core.cache import Cache, get_cache
from app.core.config import get_settings
from app.db.models import Job
from app.db.session import get_session_factory
from app.jobs.aggregator import _is_worldwide_remote
from app.jobs.catalog import normalize_skills
from app.jobs.sources import fetch_adzuna, fetch_arbeitnow, fetch_remotive, fetch_themuse
from app.jobs.taxonomy import classify_title
from app.schemas.jobs import is_safe_url

logger = logging.getLogger(__name__)

SYNC_QUERIES: dict[str, list[str]] = {
    "data": ["data analyst", "business analyst", "data engineer", "data scientist", "business intelligence"],
    "software": ["software engineer", "developer", "devops", "qa engineer"],
    "civil": ["civil engineer", "structural engineer"],
    "electrical": ["electrical engineer", "electronics engineer"],
    "mechanical": ["mechanical engineer", "industrial engineer", "textile"],
}
MAX_DESCRIPTION_CHARS = 8000
_BLOCK_TAGS = re.compile(r"</(p|div|li|h[1-6]|tr)>|<br\s*/?>", re.IGNORECASE)
_LI = re.compile(r"<li[^>]*>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    text = _LI.sub("\n• ", raw or "")
    text = _BLOCK_TAGS.sub("\n", text)
    text = html.unescape(_TAGS.sub(" ", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:MAX_DESCRIPTION_CHARS]


async def fetch_external(client: httpx.AsyncClient, cache: Cache | None = None) -> list[dict]:
    queries = [q for qs in SYNC_QUERIES.values() for q in qs]
    semaphore = asyncio.Semaphore(4)  # be polite to free public APIs

    async def run(query: str):
        async with semaphore:
            return await asyncio.gather(
                fetch_remotive(client, query, cache),
                fetch_arbeitnow(client, query, cache),
                fetch_themuse(client, query, cache),
                fetch_adzuna(client, query, "", cache),
            )

    batches = await asyncio.gather(*(run(q) for q in queries))
    return [job for per_query in batches for group in per_query for job in group]


def _workplace(job: dict) -> str:
    location = (job.get("location") or "").lower()
    if job.get("source") == "Remotive" or "remote" in location or _is_worldwide_remote(location):
        return "remote"
    return "onsite"


def upsert_external(raw_jobs: list[dict], now: datetime | None = None) -> dict:
    """Writes fetched jobs into the catalog. Sync; call from a worker thread."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    stats = {"fetched": len(raw_jobs), "created": 0, "updated": 0, "skipped": 0, "expired": 0}

    candidates: dict[tuple[str, str], dict] = {}
    for raw in raw_jobs:
        url = (raw.get("url") or "").strip()[:500]
        title = (raw.get("title") or "").strip()
        discipline = classify_title(title)
        if not url or not title or not discipline or not is_safe_url(url) or _workplace(raw) != "remote":
            stats["skipped"] += 1
            continue
        source = (raw.get("source") or "external").lower().replace(" ", "")[:30]
        candidates[(source, url)] = {**raw, "_discipline": discipline, "_source": source, "_url": url}

    with get_session_factory()() as db:
        existing = {}
        if candidates:
            rows = db.scalars(select(Job).where(Job.source.in_({s for s, _ in candidates}))).all()
            existing = {(j.source, j.external_id): j for j in rows}

        for key, raw in candidates.items():
            description = html_to_text(raw.get("description", "")) or raw["title"]
            fields = {
                "title": raw["title"].strip()[:300],
                "company": (raw.get("company") or "Unknown").strip()[:300],
                "location": (raw.get("location") or "").strip()[:200],
                "discipline": raw["_discipline"],
                "workplace": _workplace(raw),
                "description": description,
                "skills": normalize_skills([], raw["title"], description),
                "apply_url": raw["_url"],
                "last_seen_at": now,
            }
            job = existing.get(key)
            if job is None:
                db.add(Job(source=raw["_source"], external_id=raw["_url"], status="published",
                           salary_currency="USD", **fields))
                stats["created"] += 1
            else:
                for name, value in fields.items():
                    setattr(job, name, value)
                stats["updated"] += 1

        cutoff = now - timedelta(days=settings.jobs_external_max_age_days)
        stats["expired"] = db.execute(
            delete(Job).where(Job.source != "local", Job.last_seen_at < cutoff)
        ).rowcount or 0
        db.commit()
    return stats


async def sync_external_jobs(client: httpx.AsyncClient | None = None) -> dict:
    if client is None:
        async with httpx.AsyncClient(timeout=10.0) as own:
            raw = await fetch_external(own, get_cache())
    else:
        raw = await fetch_external(client, get_cache())
    loop = asyncio.get_running_loop()
    stats = await loop.run_in_executor(None, upsert_external, raw)
    logger.info("Job catalog sync: %s", stats)
    return stats


def last_external_sync() -> datetime | None:
    with get_session_factory()() as db:
        value = db.scalar(select(func.max(Job.last_seen_at)).where(Job.source != "local"))
    if value is not None and value.tzinfo is None:  # SQLite returns naive datetimes
        value = value.replace(tzinfo=UTC)
    return value


_background: set[asyncio.Task] = set()


async def maybe_schedule_sync(client: httpx.AsyncClient | None) -> bool:
    """Starts a background sync if the catalog is stale. At most one per
    instance per lock window, and the staleness check itself is cached."""
    settings = get_settings()
    if not settings.jobs_sync_enabled:
        return False
    cache = get_cache()
    if await cache.get("jobs:sync:fresh"):
        return False
    loop = asyncio.get_running_loop()
    last = await loop.run_in_executor(None, last_external_sync)
    interval = timedelta(hours=settings.jobs_sync_interval_hours)
    if last is not None and datetime.now(UTC) - last < interval:
        await cache.set("jobs:sync:fresh", True, 300)
        return False
    if await cache.incr("jobs:sync:lock", ttl_seconds=900) > 1:
        return False

    async def run():
        try:
            await sync_external_jobs(client)
        except Exception:
            logger.exception("Background job catalog sync failed")

    task = asyncio.create_task(run())
    _background.add(task)  # keep a reference so the task isn't garbage-collected
    task.add_done_callback(_background.discard)
    return True
