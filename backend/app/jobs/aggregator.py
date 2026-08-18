import asyncio
import re

import httpx

from app.jobs.sources import fetch_adzuna, fetch_arbeitnow, fetch_remotive, fetch_themuse
from app.matching.infer import get_encoder

# How much one embedding-similarity point (0-1 range) counts against one
# keyword-overlap point (integer counts). Keeps the trained encoder as an
# enhancement layered on the heuristic, not a replacement — it can surface
# jobs the keyword match misses (e.g. "BI Analyst" for a "Data Analyst"
# resume) without letting a spurious semantic match drown out real overlap.
EMBEDDING_WEIGHT = 5.0

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z+.#]{1,}")
STOPWORDS = {"and", "the", "for", "with", "of", "in", "to", "a", "an", "on", "at", "or"}


def _tokenize(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}


def _relevance(job: dict, terms: set[str]) -> float:
    if not terms:
        return 0.0
    haystack_set = _tokenize(job.get("title", "") + " " + job.get("description", ""))
    overlap = len(terms & haystack_set)
    title_overlap = len(terms & _tokenize(job.get("title", "")))
    return overlap + title_overlap * 2  # weight title matches higher


async def search_jobs(query: str, skills: list[str], location: str = "") -> list[dict]:
    async with httpx.AsyncClient() as client:
        results_lists = await asyncio.gather(
            fetch_remotive(client, query),
            fetch_arbeitnow(client, query),
            fetch_themuse(client, query),
            fetch_adzuna(client, query, location),
        )

    all_jobs = [job for group in results_lists for job in group]

    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job["title"].strip().lower(), job["company"].strip().lower())
        if key in seen or not job["title"]:
            continue
        seen.add(key)
        unique_jobs.append(job)

    terms = _tokenize(query) | {s.lower() for s in skills}
    for job in unique_jobs:
        job["relevance_score"] = _relevance(job, terms)

    encoder = get_encoder()
    if encoder is not None and unique_jobs:
        anchor_text = f"{query} skills: {', '.join(skills)}"
        anchor_emb = encoder.embed(anchor_text)
        job_texts = [
            f"{j['title']} at {j.get('company', '')}. {j.get('description', '')[:500]}"
            for j in unique_jobs
        ]
        job_embs = encoder.embed_batch(job_texts)
        similarities = job_embs @ anchor_emb
        for job, similarity in zip(unique_jobs, similarities):
            job["relevance_score"] += max(float(similarity), 0.0) * EMBEDDING_WEIGHT

    if terms:
        unique_jobs = [j for j in unique_jobs if j["relevance_score"] > 0]

    unique_jobs.sort(key=lambda j: j["relevance_score"], reverse=True)

    max_score = max((j["relevance_score"] for j in unique_jobs), default=0) or 1
    for job in unique_jobs:
        job["relevance_score"] = round(min(job["relevance_score"] / max_score, 1.0) * 100, 1)
        job.pop("description", None)

    return unique_jobs[:30]
