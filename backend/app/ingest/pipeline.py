"""Runs sources, applies one set of rules to every posting, and stores them.

Rules, in order (each rejection is counted, so a run's report explains itself):
1. title classifies into a supported discipline (engineering & data)
2. title matches a keyword, when keywords are configured
3. location fits the policy (default: remote, or in Bangladesh)
4. the apply link is http(s) — never javascript:/data:
Scraped descriptions are trimmed to a short excerpt; the full posting stays
on the source site, which is where the "Apply" button sends people.
"""

import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select

from app.db.models import Job
from app.db.session import get_session_factory
from app.ingest.adapters import FETCHERS
from app.ingest.http import PoliteClient, RobotsDisallowed
from app.ingest.models import IngestConfig, Posting, SourceConfig
from app.jobs.catalog import normalize_skills
from app.jobs.taxonomy import classify_title
from app.schemas.jobs import is_safe_url

logger = logging.getLogger(__name__)

BANGLADESH_RE = re.compile(
    r"\b(bangladesh|dhaka|chattogram|chittagong|sylhet|khulna|rajshahi|barishal|barisal|rangpur|"
    r"mymensingh|gazipur|narayanganj|savar|cumilla|comilla|bogura|bogra|ashulia|tongi)\b",
    re.IGNORECASE,
)
REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|work from home|wfh|distributed)\b", re.IGNORECASE)
HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
API_DESCRIPTION_CHARS = 6000
SCRAPED_DESCRIPTION_CHARS = 800


def workplace_of(p: Posting) -> str:
    if HYBRID_RE.search(p.location):
        return "hybrid"
    if p.remote or REMOTE_RE.search(p.location):
        return "remote"
    return "onsite"


def location_ok(p: Posting, policy: str) -> bool:
    remote = workplace_of(p) == "remote"
    in_bd = bool(BANGLADESH_RE.search(p.location))
    return {
        "any": True,
        "remote": remote,
        "bangladesh": in_bd,
        "remote_or_bangladesh": remote or in_bd,
    }[policy]


def keyword_ok(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    lowered = title.lower()
    return any(k.lower() in lowered for k in keywords)


def make_prefilter(keywords: list[str]):
    """Cheap title-only check run inside adapters, before any per-job request."""
    return lambda title: bool(title) and classify_title(title) is not None and keyword_ok(title, keywords)


def triage(postings: list[Posting], keywords: list[str], policy: str) -> tuple[list[Posting], dict]:
    reasons = {"discipline": 0, "keyword": 0, "location": 0, "url": 0}
    kept: dict[str, Posting] = {}
    for p in postings:
        if classify_title(p.title) is None:
            reasons["discipline"] += 1
        elif not keyword_ok(p.title, keywords):
            reasons["keyword"] += 1
        elif not location_ok(p, policy):
            reasons["location"] += 1
        elif not p.url or not is_safe_url(p.url):
            reasons["url"] += 1
        else:
            kept[p.url[:500]] = p  # dedupe within a source by apply link
    return list(kept.values()), reasons


def save(src: SourceConfig, postings: list[Posting], now: datetime, *, fetched: int | None = None) -> dict:
    """Upserts by (source, url). For 'complete' sources (an ATS board returns
    every open job each time), jobs missing from this successful fetch are
    removed — they were filled or withdrawn. Admin-hidden jobs stay hidden."""
    stats = {"created": 0, "updated": 0, "removed": 0}
    limit = SCRAPED_DESCRIPTION_CHARS if src.is_scraping else API_DESCRIPTION_CHARS
    with get_session_factory()() as db:
        existing = {j.external_id: j for j in db.scalars(select(Job).where(Job.source == src.source_key)).all()}
        for p in postings:
            url = p.url[:500]
            description = (p.description or p.title).strip()
            if len(description) > limit:
                description = description[:limit].rsplit(" ", 1)[0] + " …"
            fields = {
                "title": p.title.strip()[:300],
                "company": (p.company or src.company or "Unknown").strip()[:300],
                "location": p.location.strip()[:200],
                "discipline": classify_title(p.title),
                "workplace": workplace_of(p),
                "employment_type": p.employment_type or "full_time",
                "description": description,
                "skills": normalize_skills([], p.title, description),
                "apply_url": url,
                "deadline": p.deadline,
                "salary_min": p.salary_min,
                "salary_max": p.salary_max,
                "salary_currency": (p.salary_currency or "USD")[:3],
                "salary_period": p.salary_period or "year",
                "last_seen_at": now,
            }
            job = existing.get(url)
            if job is None:
                db.add(Job(source=src.source_key, external_id=url, status="published", **fields))
                stats["created"] += 1
            else:
                for name, value in fields.items():
                    setattr(job, name, value)
                stats["updated"] += 1
        # A board that suddenly returns nothing is more likely an API change
        # than every job being filled at once — don't wipe it on that signal.
        if src.complete and (fetched is None or fetched > 0):
            stats["removed"] = db.execute(
                delete(Job)
                .where(Job.source == src.source_key, Job.last_seen_at < now)
                .execution_options(synchronize_session=False)
            ).rowcount or 0
        db.commit()
    return stats


async def run_source(client: PoliteClient, cfg: IngestConfig, src: SourceConfig, *, dry_run: bool,
                     extra_keywords: list[str] | None = None) -> dict:
    report = {"source": src.name, "type": src.type, "key": src.source_key}
    if not src.enabled:
        return {**report, "status": "disabled"}
    if src.is_scraping and not src.terms_ok:
        return {**report, "status": "skipped", "reason": "terms_ok is false — confirm the site's terms allow this first"}

    keywords = [*cfg.keywords, *src.keywords, *(extra_keywords or [])]
    policy = src.location_policy or cfg.location_policy
    now = datetime.now(UTC)
    try:
        fetched = await FETCHERS[src.type](client, src, make_prefilter(keywords))
    except RobotsDisallowed as exc:
        return {**report, "status": "blocked_by_robots", "url": str(exc)}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Source %s failed: %s", src.name, exc)
        return {**report, "status": "error", "error": f"{type(exc).__name__}: {exc}"[:300]}

    kept, rejected = triage(fetched, keywords, policy)
    report.update(status="ok", fetched=len(fetched), kept=len(kept), rejected=rejected,
                  sample=[f"{p.title} — {p.company} ({p.location or 'n/a'})" for p in kept[:5]])
    if not dry_run:
        report.update(save(src, kept, now, fetched=len(fetched)))
    return report
