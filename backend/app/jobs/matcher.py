"""Ranks open jobs against a resume.

Score per job (0–100), each component in 0–1, weights renormalized when a
component is unavailable:

    skills      0.50  share of the job's skills the resume has (cap 12 skills,
                      so a posting that name-drops 30 tools isn't unwinnable)
    text        0.25  TF-IDF cosine between resume and posting
    semantic    0.15  trained encoder similarity (catches "BI Analyst" for a
                      "Data Analyst" resume with no literal overlap)
    experience  0.10  years on the resume vs. the posting's requirement

The job side (TF-IDF matrix, encoder embeddings, skill sets) is built once
per catalog version and cached in-process, so a match request costs one
vectorization of the resume plus a dot product per job — not a model fit.
"""

import threading
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import func, select

from app.analysis.profile_extractor import extract_skills, extract_years_experience
from app.analysis.skills_data import SOFT_SKILLS
from app.builder.layout import render_text
from app.core.config import get_settings
from app.db.models import Job
from app.db.session import get_session_factory
from app.jobs.catalog import job_to_dict, open_condition, today
from app.jobs.taxonomy import classify_profile
from app.matching.infer import get_encoder
from app.schemas.resume import ResumeDocument

WEIGHTS = {"skills": 0.50, "text": 0.25, "semantic": 0.15, "experience": 0.10}
SKILL_DENOMINATOR_CAP = 12
TEXT_SIM_FULL_CREDIT = 0.30  # TF-IDF cosine at which text similarity counts as a full match
MAX_MISSING_SHOWN = 8

# Soft skills go last in "missing" lists: "communication" is a weaker gap to
# report than "power bi" when both are absent.
_SOFT = SOFT_SKILLS


@dataclass
class _Index:
    fingerprint: tuple
    jobs: list[dict] = field(default_factory=list)
    skills: list[set[str]] = field(default_factory=list)
    vectorizer: TfidfVectorizer | None = None
    matrix: object | None = None
    embeddings: np.ndarray | None = None


_index: _Index | None = None
_lock = threading.Lock()


def _job_text(job: Job) -> str:
    return f"{job.title}\n{job.title}\n{' '.join(job.skills or [])}\n{job.description[:4000]}"


def _fingerprint(db) -> tuple:
    count, latest = db.execute(
        select(func.count(), func.max(Job.updated_at)).where(open_condition())
    ).one()
    return (str(db.get_bind().url), today().isoformat(), count, str(latest))


def _build(db, fingerprint) -> _Index:
    rows = db.scalars(
        select(Job).where(open_condition()).order_by(Job.created_at.desc()).limit(get_settings().jobs_match_candidates)
    ).all()
    index = _Index(fingerprint=fingerprint)
    if not rows:
        return index
    index.jobs = [job_to_dict(j) for j in rows]
    index.skills = [set(j.skills or []) for j in rows]
    index.vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2), max_features=50_000)
    index.matrix = index.vectorizer.fit_transform([_job_text(j) for j in rows])
    encoder = get_encoder()
    if encoder is not None:
        index.embeddings = encoder.embed_batch([f"{j.title} at {j.company}. {j.description[:500]}" for j in rows])
    return index


def get_index() -> _Index:
    global _index
    with get_session_factory()() as db:
        fingerprint = _fingerprint(db)
        with _lock:
            if _index is None or _index.fingerprint != fingerprint:
                _index = _build(db, fingerprint)
            return _index


def reset_index() -> None:
    global _index
    with _lock:
        _index = None


def _experience_fit(years: float | None, minimum: float | None, maximum: float | None) -> tuple[float, str | None]:
    if minimum is None or minimum <= 0:
        return 1.0, None
    if years is None:
        return 0.6, f"Asks for {minimum:g}+ years; add dates to your roles so this can be checked."
    if years >= minimum:
        if maximum is not None and years > maximum + 3:
            return 0.8, f"Targets {minimum:g}–{maximum:g} years; you may be overqualified."
        return 1.0, None
    gap = minimum - years
    return max(0.0, 1 - gap / max(minimum, 1)), f"Asks for {minimum:g}+ years; your resume shows about {years:g}."


def _passes(job: dict, discipline, workplace, source, q) -> bool:
    if discipline and job["discipline"] != discipline:
        return False
    if workplace and job["workplace"] != workplace:
        return False
    if source == "local" and job["source"] != "local":
        return False
    if source == "remote" and job["source"] == "local":
        return False
    if q:
        needle = q.lower()
        if not any(needle in (job[f] or "").lower() for f in ("title", "company", "location")):
            return False
    return True


def match_document(
    doc: ResumeDocument, *, discipline=None, workplace=None, source=None, q=None, limit: int = 20
) -> dict:
    text = render_text(doc)
    title = next((e.title for e in doc.experience if e.title), None) or doc.basics.headline or None
    profile_skills = {s.lower() for s in doc.all_skills()} | set(extract_skills(text))
    years = extract_years_experience(text)
    profile = {
        "title": title,
        "years_experience": years,
        "skills": sorted(profile_skills),
        "detected_discipline": classify_profile(title, list(profile_skills)),
    }

    index = get_index()
    if not index.jobs or not text.strip():
        return {"profile": profile, "total_considered": 0, "results": []}

    text_sims = (index.matrix @ index.vectorizer.transform([text]).T).toarray().ravel()
    semantic = None
    encoder = get_encoder()
    if index.embeddings is not None and encoder is not None:
        anchor = encoder.embed(f"{title or ''} skills: {', '.join(sorted(profile_skills))}")
        semantic = index.embeddings @ anchor

    results = []
    for i, job in enumerate(index.jobs):
        if not _passes(job, discipline, workplace, source, q):
            continue
        job_skills = index.skills[i]
        matched = job_skills & profile_skills
        missing = job_skills - profile_skills
        denominator = min(len(job_skills), SKILL_DENOMINATOR_CAP)
        exp_score, exp_note = _experience_fit(years, job["experience_min"], job["experience_max"])
        components = {
            "skills": min(1.0, len(matched) / denominator) if denominator else None,
            "text": min(1.0, float(text_sims[i]) / TEXT_SIM_FULL_CREDIT),
            "semantic": max(0.0, float(semantic[i])) if semantic is not None else None,
            "experience": exp_score,
        }
        available = {k: v for k, v in components.items() if v is not None}
        weight_sum = sum(WEIGHTS[k] for k in available)
        score = 100 * sum(WEIGHTS[k] * v for k, v in available.items()) / weight_sum
        results.append({
            "job": job,
            "match_score": round(score, 1),
            "matched_skills": sorted(matched),
            "missing_skills": sorted(missing, key=lambda s: (s in _SOFT, s))[:MAX_MISSING_SHOWN],
            "experience_note": exp_note,
            "components": {k: (round(v, 3) if v is not None else None) for k, v in components.items()},
        })

    results.sort(key=lambda r: (r["match_score"], r["job"]["created_at"]), reverse=True)
    return {"profile": profile, "total_considered": len(results), "results": results[:limit]}
