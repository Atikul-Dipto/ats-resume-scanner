"""Job-board providers. Documented public APIs only — no scraping.

Each fetcher takes an optional cache. External APIs are the slowest and least
reliable dependency in the system, and two of them (Arbeitnow, The Muse)
return a whole feed regardless of the query, so their raw feed is cached
once and filtered locally per query rather than re-downloaded per search.
"""

import re

import httpx

from app.core.cache import Cache
from app.core.config import get_settings

TIMEOUT = 10.0
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z+.#]{1,}")


def _query_terms(query: str) -> set[str]:
    return set(WORD_RE.findall(query.lower()))


def _normalize(query: str) -> str:
    return " ".join(sorted(_query_terms(query)))


async def _cached(cache: Cache | None, key: str, loader):
    if cache is None:
        return await loader()
    hit = await cache.get(key)
    if hit is not None:
        return hit
    value = await loader()
    # Don't cache an empty result: it's usually a provider outage, and
    # caching it would hide the provider for the whole TTL.
    if value:
        await cache.set(key, value, get_settings().jobs_cache_ttl_seconds)
    return value


async def fetch_remotive(client: httpx.AsyncClient, query: str, cache: Cache | None = None) -> list[dict]:
    async def load():
        try:
            resp = await client.get(
                "https://remotive.com/api/remote-jobs", params={"search": query}, timeout=TIMEOUT
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])[:25]
        except (httpx.HTTPError, ValueError):
            return []
        return [
            {
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote"),
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "source": "Remotive",
            }
            for j in jobs
        ]

    return await _cached(cache, f"jobs:remotive:{_normalize(query)}", load)


async def _arbeitnow_feed(client: httpx.AsyncClient, cache: Cache | None) -> list[dict]:
    async def load():
        try:
            resp = await client.get("https://www.arbeitnow.com/api/job-board-api", timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except (httpx.HTTPError, ValueError):
            return []

    return await _cached(cache, "feed:arbeitnow", load)


async def fetch_arbeitnow(client: httpx.AsyncClient, query: str, cache: Cache | None = None) -> list[dict]:
    jobs = await _arbeitnow_feed(client, cache)
    query_terms = _query_terms(query)

    def is_relevant(job: dict) -> bool:
        haystack = (job.get("title", "") + " " + " ".join(job.get("tags", []))).lower()
        return any(term in haystack for term in query_terms)

    matches = [j for j in jobs if not query_terms or is_relevant(j)][:25]
    return [
        {
            "title": j.get("title", ""),
            "company": j.get("company_name", ""),
            "location": j.get("location") or ("Remote" if j.get("remote") else ""),
            "url": j.get("url", ""),
            "description": j.get("description", ""),
            "source": "Arbeitnow",
        }
        for j in matches
    ]


async def _themuse_feed(client: httpx.AsyncClient, cache: Cache | None) -> list[dict]:
    async def load():
        try:
            resp = await client.get(
                "https://www.themuse.com/api/public/jobs", params={"page": 0}, timeout=TIMEOUT
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return []

    return await _cached(cache, "feed:themuse", load)


async def fetch_themuse(client: httpx.AsyncClient, query: str, cache: Cache | None = None) -> list[dict]:
    jobs = await _themuse_feed(client, cache)
    query_terms = _query_terms(query)

    def is_relevant(job: dict) -> bool:
        return not query_terms or any(term in job.get("name", "").lower() for term in query_terms)

    results = []
    for j in [j for j in jobs if is_relevant(j)][:25]:
        results.append({
            "title": j.get("name", ""),
            "company": j.get("company", {}).get("name", ""),
            "location": ", ".join(loc.get("name", "") for loc in j.get("locations", [])),
            "url": j.get("refs", {}).get("landing_page", ""),
            "description": j.get("contents", ""),
            "source": "The Muse",
        })
    return results


async def fetch_adzuna(
    client: httpx.AsyncClient, query: str, location: str = "", cache: Cache | None = None
) -> list[dict]:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []

    async def load():
        try:
            resp = await client.get(
                f"https://api.adzuna.com/v1/api/jobs/{settings.adzuna_country}/search/1",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": query,
                    "where": location,
                    "results_per_page": 25,
                    "content-type": "application/json",
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            jobs = resp.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return []
        return [
            {
                "title": j.get("title", ""),
                "company": j.get("company", {}).get("display_name", ""),
                "location": j.get("location", {}).get("display_name", ""),
                "url": j.get("redirect_url", ""),
                "description": j.get("description", ""),
                "source": "Adzuna",
            }
            for j in jobs
        ]

    key = f"jobs:adzuna:{settings.adzuna_country}:{_normalize(query)}:{location.strip().lower()}"
    return await _cached(cache, key, load)
