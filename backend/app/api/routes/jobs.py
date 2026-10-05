import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.executor import run_cpu_bound
from app.core.rate_limit import rate_limit
from app.db.models import Job
from app.jobs.aggregator import search_jobs
from app.jobs.catalog import job_to_dict, list_open_jobs, open_condition
from app.jobs.catalog_sync import maybe_schedule_sync
from app.jobs.matcher import match_document
from app.matching.store import log_match_events
from app.schemas.analysis import JobSearchResponse
from app.schemas.jobs import Discipline, EmploymentType, JobListOut, JobOut, MatchOut, MatchRequest, Workplace

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def refresh_catalog_if_stale(request: Request) -> None:
    """Kicks off a background import of remote jobs when the catalog is stale.
    Never blocks the request: it reads whatever is in the catalog right now."""
    await maybe_schedule_sync(getattr(request.app.state, "http", None))


@router.get("", response_model=JobListOut, dependencies=[Depends(refresh_catalog_if_stale)])
def list_jobs(
    db: DbSession,
    discipline: Discipline | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    workplace: Workplace | None = None,
    employment_type: EmploymentType | None = None,
    source: Literal["local", "remote"] | None = None,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    return list_open_jobs(
        db, discipline=discipline, q=(q or "").strip() or None, workplace=workplace,
        employment_type=employment_type, source=source, page=page, page_size=page_size,
    )


@router.post(
    "/match",
    response_model=MatchOut,
    dependencies=[Depends(rate_limit("match")), Depends(refresh_catalog_if_stale)],
)
async def match_jobs(body: MatchRequest):
    """Ranks open jobs against a resume. The resume travels in the body (from
    the builder, a saved resume, or a scanned upload's draft) and isn't stored."""
    return await run_cpu_bound(
        match_document, body.document, discipline=body.discipline, workplace=body.workplace,
        source=body.source, q=body.q, limit=body.limit,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: DbSession):
    job = db.scalar(select(Job).where(Job.id == job_id, open_condition()))
    if job is None:
        raise HTTPException(404, "This job is no longer available.")
    return job_to_dict(job, with_description=True)


@router.post("/search", response_model=JobSearchResponse, dependencies=[Depends(rate_limit("jobs"))])
async def jobs_search(
    request: Request,
    background: BackgroundTasks,
    query: Annotated[str, Form(min_length=1, max_length=200)],
    skills: Annotated[str, Form(max_length=3000)] = "",
    location: Annotated[str, Form(max_length=100)] = "",
):
    settings = get_settings()
    skill_list = [s.strip() for s in skills.split(",") if s.strip()][:60]
    try:
        results = await asyncio.wait_for(
            search_jobs(query, skill_list, location, client=request.app.state.http, cache=get_cache()),
            timeout=settings.jobs_search_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(504, "The job boards are responding slowly — please try again.") from exc

    if settings.events_enabled and results:
        background.add_task(log_match_events, query, skill_list, results[:3])
    return {"query": query, "results": results}
