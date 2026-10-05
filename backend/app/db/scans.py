from app.db.models import Scan
from app.db.session import get_session_factory


def record_scan(
    user_id: str,
    result: dict,
    *,
    source: str,
    had_job_description: bool,
    filename: str | None = None,
    resume_id: str | None = None,
) -> None:
    """Adds a row to a signed-in user's score history. Runs as a background task."""
    with get_session_factory()() as db:
        db.add(Scan(
            user_id=user_id,
            resume_id=resume_id,
            source=source,
            filename=(filename or None) and filename[:255],
            ats_score=result["ats_score"],
            formatting_score=result["formatting_score"],
            content_score=result["content_score"],
            keyword_score=result["keyword_score"],
            had_job_description=had_job_description,
        ))
        db.commit()
