"""Saved resumes — the account-backed half of the builder."""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select, update

from app.analysis.pipeline import analyze_document
from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.models import Resume, Scan
from app.db.scans import record_scan
from app.schemas.api import ResumeCreate, ResumeOut, ResumeSummary, ResumeUpdate, ScanOut
from app.schemas.resume import ResumeDocument

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _owned(db, user_id: str, resume_id: str) -> Resume:
    # 404 (not 403) for someone else's resume: don't confirm that the id exists.
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise HTTPException(404, "Resume not found.")
    return resume


def _score(document: ResumeDocument, job_description: str | None) -> dict:
    return analyze_document(document, job_description)


def _check_quota(db, user_id: str) -> None:
    limit = get_settings().max_resumes_per_user
    count = db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))
    if count >= limit:
        raise HTTPException(409, f"You can save up to {limit} resumes. Delete one to make room.")


@router.get("", response_model=list[ResumeSummary])
def list_resumes(user: CurrentUser, db: DbSession):
    return db.scalars(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.updated_at.desc())
    ).all()


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def create_resume(body: ResumeCreate, user: CurrentUser, db: DbSession, background: BackgroundTasks):
    _check_quota(db, user.id)
    result = _score(body.document, body.target_job_description)
    resume = Resume(
        user_id=user.id,
        title=body.title,
        document=body.document.model_dump(),
        target_job_description=body.target_job_description,
        last_score=result["ats_score"],
    )
    db.add(resume)
    db.commit()
    background.add_task(record_scan, user.id, result, source="builder", resume_id=resume.id,
                        had_job_description=bool(body.target_job_description))
    return resume


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: str, user: CurrentUser, db: DbSession):
    return _owned(db, user.id, resume_id)


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(resume_id: str, body: ResumeUpdate, user: CurrentUser, db: DbSession, background: BackgroundTasks):
    existing = _owned(db, user.id, resume_id)
    previous_score = existing.last_score
    result = _score(body.document, body.target_job_description)

    # Compare-and-swap on version in a single UPDATE, so two concurrent saves
    # can't both succeed — the loser gets a 409 and reloads.
    outcome = db.execute(
        update(Resume)
        .where(Resume.id == resume_id, Resume.user_id == user.id, Resume.version == body.version)
        .values(
            title=body.title,
            document=body.document.model_dump(),
            target_job_description=body.target_job_description,
            last_score=result["ats_score"],
            version=Resume.version + 1,
            updated_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    if outcome.rowcount == 0:
        db.rollback()
        raise HTTPException(409, "This resume was changed elsewhere (another tab or device). Reload to get the latest version.")
    db.commit()
    db.refresh(existing)

    if result["ats_score"] != previous_score:
        background.add_task(record_scan, user.id, result, source="builder", resume_id=resume_id,
                            had_job_description=bool(body.target_job_description))
    return existing


@router.post("/{resume_id}/duplicate", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def duplicate_resume(resume_id: str, user: CurrentUser, db: DbSession):
    source = _owned(db, user.id, resume_id)
    _check_quota(db, user.id)
    copy = Resume(
        user_id=user.id,
        title=f"{source.title} (copy)"[:200],
        document=source.document,
        target_job_description=source.target_job_description,
        last_score=source.last_score,
    )
    db.add(copy)
    db.commit()
    return copy


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: str, user: CurrentUser, db: DbSession):
    db.delete(_owned(db, user.id, resume_id))
    db.commit()


@router.get("/{resume_id}/scans", response_model=list[ScanOut])
def resume_scans(resume_id: str, user: CurrentUser, db: DbSession):
    _owned(db, user.id, resume_id)
    return db.scalars(
        select(Scan).where(Scan.resume_id == resume_id).order_by(Scan.created_at.desc()).limit(50)
    ).all()
