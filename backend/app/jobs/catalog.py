"""Job catalog queries — the one definition of "an open listing" and its filters."""

from datetime import UTC, date, datetime

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.analysis.profile_extractor import extract_skills
from app.db.models import Job

SNIPPET_CHARS = 220


def today() -> date:
    return datetime.now(UTC).date()


def open_condition(on: date | None = None):
    """Published and not past its deadline."""
    on = on or today()
    return (Job.status == "published") & or_(Job.deadline.is_(None), Job.deadline >= on)


def normalize_skills(explicit: list[str], title: str, description: str) -> list[str]:
    """Admin-listed skills first, then vocabulary skills mentioned in the posting."""
    combined = [s.strip().lower() for s in explicit if s.strip()] + extract_skills(f"{title}\n{description}")
    return list(dict.fromkeys(combined))[:60]


def snippet(description: str) -> str:
    text = " ".join(description.split())
    return text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


def job_to_dict(job: Job, *, with_description: bool = False) -> dict:
    data = {
        "id": job.id,
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "discipline": job.discipline,
        "employment_type": job.employment_type,
        "workplace": job.workplace,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "salary_period": job.salary_period,
        "skills": job.skills or [],
        "apply_url": job.apply_url,
        "deadline": job.deadline,
        "status": job.status,
        "created_at": job.created_at,
        "snippet": snippet(job.description),
    }
    if with_description:
        data["description"] = job.description
        data["updated_at"] = job.updated_at
    return data


def _like(term: str) -> str:
    escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def apply_filters(stmt, *, q=None, workplace=None, employment_type=None, source=None, skill=None):
    if q:
        pattern = _like(q)
        stmt = stmt.where(or_(
            func.lower(Job.title).like(pattern, escape="\\"),
            func.lower(Job.company).like(pattern, escape="\\"),
            func.lower(Job.location).like(pattern, escape="\\"),
        ))
    if skill:
        # skills is a JSON list of normalized lowercase names; match one whole entry.
        stmt = stmt.where(func.lower(cast(Job.skills, String)).like(_like(f'"{skill.lower()}"'), escape="\\"))
    if workplace:
        stmt = stmt.where(Job.workplace == workplace)
    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type)
    if source == "local":
        stmt = stmt.where(Job.source == "local")
    elif source == "remote":
        stmt = stmt.where(Job.source != "local")
    return stmt


# Listings posted here (local, Bangladesh-focused) rank above imported remote ones.
LOCAL_FIRST = case((Job.source == "local", 0), else_=1)


def list_open_jobs(db: Session, *, discipline=None, page=1, page_size=20, **filters) -> dict:
    base = apply_filters(select(Job).where(open_condition()), **filters)
    facet_rows = db.execute(
        apply_filters(select(Job.discipline, func.count()).where(open_condition()), **filters).group_by(Job.discipline)
    ).all()
    facets = {d: n for d, n in facet_rows}

    if discipline:
        base = base.where(Job.discipline == discipline)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    jobs = db.scalars(
        base.order_by(LOCAL_FIRST, Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [job_to_dict(j) for j in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "facets": facets,
    }
