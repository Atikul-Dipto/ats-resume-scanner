"""Builds a real, honestly-sourced training corpus for the matching encoder.

There is no historical hiring-outcome data available, and no resume corpus
(the app never persists raw resumes). So training starts from a self-supervised
bootstrap: for each real job posting, the (title + skill tags) form a short
"profile-like" view and the full description forms a longer "job-like" view of
the *same* posting. Training the encoder to align these two views of the same
job teaches it which titles/skills/descriptions cluster together semantically
— the same structure a real resume vs. job-description pair would need — without
fabricating labels that don't exist.

As real usage accumulates (see matching/store.py), those anonymized
(profile, job, heuristic-score) events become a second, real-usage training
signal that supplements this bootstrap on retrain.
"""

import asyncio
import re

import httpx

from app.jobs.sources import fetch_arbeitnow, fetch_remotive, fetch_themuse

# Diverse on purpose: Remotive skews tech/remote, so we widen coverage with
# queries spanning non-tech roles too, to avoid a narrowly tech-biased vocabulary.
BOOTSTRAP_QUERIES = [
    "data analyst", "software engineer", "product manager", "marketing manager",
    "sales representative", "customer support", "accountant", "graphic designer",
    "operations manager", "project manager", "human resources", "recruiter",
    "nurse", "supply chain", "financial analyst", "content writer",
]

WHITESPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")  # strip HTML from job descriptions
    return WHITESPACE_RE.sub(" ", text).strip()


async def fetch_training_jobs() -> list[dict]:
    """Fetches real job postings across a diverse set of queries and dedupes them."""
    seen = set()
    jobs: list[dict] = []

    async with httpx.AsyncClient() as client:
        for query in BOOTSTRAP_QUERIES:
            results = await asyncio.gather(
                fetch_remotive(client, query),
                fetch_arbeitnow(client, query),
                fetch_themuse(client, query),
            )
            for group in results:
                for job in group:
                    key = (job["title"].strip().lower(), job["company"].strip().lower())
                    if key in seen or not job.get("title") or not job.get("description"):
                        continue
                    seen.add(key)
                    jobs.append(job)

    return jobs


def build_pairs(jobs: list[dict]) -> list[tuple[str, str]]:
    """Builds (anchor, positive) text pairs: short profile-like view vs. full job view."""
    pairs = []
    for job in jobs:
        anchor = _clean(f"{job['title']} at {job.get('company', '')}")
        positive = _clean(job["description"])[:1200]
        if len(anchor) < 5 or len(positive) < 40:
            continue
        pairs.append((anchor, positive))
    return pairs
