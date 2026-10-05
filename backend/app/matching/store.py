"""Anonymized event log powering the retraining flywheel.

Two tables in the main database (see app/db/models.py):
- match_events: logged from /api/jobs/search — skills/title/years plus
  which job it matched against.
- resume_scan_events: logged from /api/analyze and resume saves — skills/
  title/years plus the resulting ATS scores, one row per scan.

Never raw resume text, name, email, or phone — those never reach this
module, and neither does a user id: events can't be tied back to an account.

Writes are called from FastAPI BackgroundTasks, after the response has been
sent, so logging never adds latency to (or fails) a user-facing request.
"""

from sqlalchemy import func, select

from app.db.models import MatchEvent, ResumeScanEvent
from app.db.session import get_session_factory


def log_event(
    resume_title: str | None,
    skills: list[str],
    years_experience: float | None,
    job_title: str,
    job_company: str,
    job_source: str,
    relevance_score: float,
) -> None:
    with get_session_factory()() as db:
        db.add(MatchEvent(
            resume_title=(resume_title or None) and resume_title[:200],
            skills=skills[:60],
            years_experience=years_experience,
            job_title=job_title[:300],
            job_company=(job_company or "")[:300],
            job_source=job_source,
            relevance_score=relevance_score,
        ))
        db.commit()


def log_match_events(resume_title: str, skills: list[str], jobs: list[dict]) -> None:
    for job in jobs:
        log_event(
            resume_title=resume_title,
            skills=skills,
            years_experience=None,
            job_title=job["title"],
            job_company=job["company"],
            job_source=job["source"],
            relevance_score=job["relevance_score"],
        )


def fetch_events(limit: int = 5000) -> list[dict]:
    with get_session_factory()() as db:
        rows = db.scalars(select(MatchEvent).order_by(MatchEvent.id.desc()).limit(limit)).all()
    return [
        {
            "resume_title": row.resume_title,
            "skills": row.skills,
            "years_experience": row.years_experience,
            "job_title": row.job_title,
            "job_company": row.job_company,
            "job_source": row.job_source,
            "relevance_score": row.relevance_score,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def event_count() -> int:
    with get_session_factory()() as db:
        return db.scalar(select(func.count()).select_from(MatchEvent)) or 0


def log_resume_scan(
    title: str | None,
    skills: list[str],
    years_experience: float | None,
    ats_score: float,
    formatting_score: float,
    content_score: float,
    keyword_score: float,
    had_job_description: bool,
) -> None:
    with get_session_factory()() as db:
        db.add(ResumeScanEvent(
            title=(title or None) and title[:200],
            skills=skills[:60],
            years_experience=years_experience,
            ats_score=ats_score,
            formatting_score=formatting_score,
            content_score=content_score,
            keyword_score=keyword_score,
            had_job_description=had_job_description,
        ))
        db.commit()


def log_analysis(result: dict, had_job_description: bool) -> None:
    profile = result["profile"]
    log_resume_scan(
        title=profile["current_title"],
        skills=profile["skills"],
        years_experience=profile["years_experience"],
        ats_score=result["ats_score"],
        formatting_score=result["formatting_score"],
        content_score=result["content_score"],
        keyword_score=result["keyword_score"],
        had_job_description=had_job_description,
    )


def fetch_resume_scans(limit: int = 5000) -> list[dict]:
    with get_session_factory()() as db:
        rows = db.scalars(select(ResumeScanEvent).order_by(ResumeScanEvent.id.desc()).limit(limit)).all()
    return [
        {
            "title": row.title,
            "skills": row.skills,
            "years_experience": row.years_experience,
            "ats_score": row.ats_score,
            "formatting_score": row.formatting_score,
            "content_score": row.content_score,
            "keyword_score": row.keyword_score,
            "had_job_description": row.had_job_description,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def resume_scan_count() -> int:
    with get_session_factory()() as db:
        return db.scalar(select(func.count()).select_from(ResumeScanEvent)) or 0
