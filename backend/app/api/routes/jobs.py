import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.jobs.aggregator import search_jobs
from app.matching.store import log_match_events
from app.schemas.analysis import JobSearchResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


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
