import os
import re

import httpx

TIMEOUT = 10.0
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z+.#]{1,}")


def _query_terms(query: str) -> set[str]:
    return set(WORD_RE.findall(query.lower()))


async def fetch_remotive(client: httpx.AsyncClient, query: str) -> list[dict]:
    try:
        resp = await client.get(
            "https://remotive.com/api/remote-jobs", params={"search": query}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])[:25]
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
    except (httpx.HTTPError, ValueError):
        return []


async def fetch_arbeitnow(client: httpx.AsyncClient, query: str) -> list[dict]:
    try:
        resp = await client.get("https://www.arbeitnow.com/api/job-board-api", timeout=TIMEOUT)
        resp.raise_for_status()
        jobs = resp.json().get("data", [])
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
    except (httpx.HTTPError, ValueError):
        return []


async def fetch_themuse(client: httpx.AsyncClient, query: str) -> list[dict]:
    try:
        resp = await client.get(
            "https://www.themuse.com/api/public/jobs", params={"page": 0}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        jobs = resp.json().get("results", [])
        query_terms = _query_terms(query)

        def is_relevant(job: dict) -> bool:
            return not query_terms or any(term in job.get("name", "").lower() for term in query_terms)

        matches = [j for j in jobs if is_relevant(j)][:25]
        results = []
        for j in matches:
            company = j.get("company", {}).get("name", "")
            locations = ", ".join(loc.get("name", "") for loc in j.get("locations", []))
            results.append({
                "title": j.get("name", ""),
                "company": company,
                "location": locations,
                "url": j.get("refs", {}).get("landing_page", ""),
                "description": j.get("contents", ""),
                "source": "The Muse",
            })
        return results
    except (httpx.HTTPError, ValueError):
        return []


async def fetch_adzuna(client: httpx.AsyncClient, query: str, location: str = "") -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    country = os.getenv("ADZUNA_COUNTRY", "us")
    try:
        resp = await client.get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params={
                "app_id": app_id,
                "app_key": app_key,
                "what": query,
                "where": location,
                "results_per_page": 25,
                "content-type": "application/json",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        jobs = resp.json().get("results", [])
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
    except (httpx.HTTPError, ValueError):
        return []
