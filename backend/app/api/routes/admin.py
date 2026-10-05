"""Admin-only job management. Admins are configured with ADMIN_EMAILS."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.db.models import Job
from app.jobs.catalog import LOCAL_FIRST, apply_filters, job_to_dict, normalize_skills
from app.jobs.catalog_sync import sync_external_jobs
from app.schemas.jobs import Discipline, JobIn, JobOut, JobStatus, JobStatusIn

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get(db, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return job


@router.get("/jobs")
def admin_list_jobs(
    _: AdminUser,
    db: DbSession,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    source: Literal["local", "remote"] | None = "local",
    discipline: Discipline | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    stmt = apply_filters(select(Job), q=(q or "").strip() or None, source=source)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if discipline:
        stmt = stmt.where(Job.discipline == discipline)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    jobs = db.scalars(stmt.order_by(LOCAL_FIRST, Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [job_to_dict(j, with_description=True) for j in jobs], "total": total, "page": page, "page_size": page_size}


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def admin_create_job(body: JobIn, admin: AdminUser, db: DbSession):
    data = body.model_dump()
    data["skills"] = normalize_skills(body.skills, body.title, body.description)
    job = Job(**data, source="local", created_by=admin.id)
    db.add(job)
    db.commit()
    return job_to_dict(job, with_description=True)


@router.get("/jobs/{job_id}", response_model=JobOut)
def admin_get_job(job_id: str, _: AdminUser, db: DbSession):
    return job_to_dict(_get(db, job_id), with_description=True)


@router.put("/jobs/{job_id}", response_model=JobOut)
def admin_update_job(job_id: str, body: JobIn, _: AdminUser, db: DbSession):
    job = _get(db, job_id)
    if job.source != "local":
        raise HTTPException(409, "Imported jobs can't be edited — they're refreshed from their source. You can hide them instead.")
    data = body.model_dump()
    data["skills"] = normalize_skills(body.skills, body.title, body.description)
    for name, value in data.items():
        setattr(job, name, value)
    db.commit()
    return job_to_dict(job, with_description=True)


@router.post("/jobs/{job_id}/status", response_model=JobOut)
def admin_set_status(job_id: str, body: JobStatusIn, _: AdminUser, db: DbSession):
    """Publish / close a listing. Works for imported jobs too, and a hidden
    imported job stays hidden across syncs."""
    job = _get(db, job_id)
    job.status = body.status
    db.commit()
    return job_to_dict(job, with_description=True)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_job(job_id: str, _: AdminUser, db: DbSession):
    job = _get(db, job_id)
    if job.source != "local":
        raise HTTPException(409, "Imported jobs would be re-imported on the next sync — hide them instead.")
    db.delete(job)
    db.commit()


@router.post("/jobs/sync")
async def admin_sync_jobs(request: Request, _: AdminUser):
    """Imports remote jobs now instead of waiting for the background refresh."""
    return await sync_external_jobs(getattr(request.app.state, "http", None))
