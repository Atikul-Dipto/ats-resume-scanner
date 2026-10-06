"""Work Signal: where the job market is moving, computed from Prottoy's own
open jobs (ingested sources plus admin posts). Every number here comes from
real listings, and every ranked item maps back to a filter on /jobs, so the
dashboard is a way into the postings rather than a picture of them.

Counts are over open jobs. "New" means first seen by Prottoy, which for an
imported job is when ingestion found it, not the employer's post date.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job
from app.jobs.catalog import LOCAL_FIRST, apply_filters, job_to_dict, open_condition
from app.jobs.locations import in_bangladesh
from app.jobs.taxonomy import DISCIPLINES

TOP_SKILLS = 12
TOP_COMPANIES = 8
TOP_LOCATIONS = 6
WEEKS = 8
MIN_SALARY_SAMPLES = 3
TREND_DAYS = 14


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _location_label(job: Job) -> str:
    if job.workplace == "remote":
        return "Remote"
    return (job.location or "").split(",")[0].strip() or "Unspecified"


def _monthly_bdt_midpoint(job: Job) -> float | None:
    if job.salary_currency != "BDT" or (job.salary_min is None and job.salary_max is None):
        return None
    values = [v for v in (job.salary_min, job.salary_max) if v is not None]
    mid = sum(values) / len(values)
    return mid / 12 if job.salary_period == "year" else mid


def compute_market(db: Session, *, discipline=None, workplace=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    stmt = apply_filters(select(Job).where(open_condition()), workplace=workplace)
    if discipline:
        stmt = stmt.where(Job.discipline == discipline)
    jobs = db.scalars(stmt).all()

    recent_cut = now - timedelta(days=TREND_DAYS)
    previous_cut = now - timedelta(days=2 * TREND_DAYS)
    skills_now, skills_before, skills_all = Counter(), Counter(), Counter()
    companies, locations, disciplines, workplaces = Counter(), Counter(), Counter(), Counter()
    weekly = [0] * WEEKS
    salaries: dict[str, list[float]] = {}
    new_7d = local = 0

    for job in jobs:
        created = _aware(job.created_at)
        skills = set(job.skills or [])
        skills_all.update(skills)
        if created >= recent_cut:
            skills_now.update(skills)
        elif created >= previous_cut:
            skills_before.update(skills)
        companies[job.company] += 1
        locations[_location_label(job)] += 1
        disciplines[job.discipline] += 1
        workplaces[job.workplace] += 1
        if created >= now - timedelta(days=7):
            new_7d += 1
        if job.workplace != "remote" and in_bangladesh(job.location or ""):
            local += 1
        week = (now - created).days // 7
        if 0 <= week < WEEKS:
            weekly[WEEKS - 1 - week] += 1
        pay = _monthly_bdt_midpoint(job)
        if pay is not None:
            salaries.setdefault(job.discipline, []).append(pay)

    total = len(jobs)
    all_pay = [p for values in salaries.values() for p in values]
    latest = db.scalars(stmt.order_by(LOCAL_FIRST, Job.created_at.desc()).limit(8)).all()
    week_starts = [(now - timedelta(days=7 * (WEEKS - 1 - i))).date() for i in range(WEEKS)]

    return {
        "generated_at": now,
        "totals": {
            "open_jobs": total,
            "companies": len(companies),
            "new_7d": new_7d,
            "local_jobs": local,
            "remote_jobs": workplaces["remote"],
            "with_salary": len(all_pay),
        },
        "skills": [
            {"name": name, "count": count, "recent": skills_now[name], "previous": skills_before[name]}
            for name, count in skills_all.most_common(TOP_SKILLS)
        ],
        "companies": [{"name": n, "count": c} for n, c in companies.most_common(TOP_COMPANIES)],
        "locations": [{"name": n, "count": c} for n, c in locations.most_common(TOP_LOCATIONS)],
        "disciplines": [{"key": key, "count": disciplines[key]} for key in DISCIPLINES],
        "workplaces": [{"key": key, "count": workplaces[key]} for key in ("onsite", "hybrid", "remote")],
        "weekly_new": [{"week_start": start, "count": count} for start, count in zip(week_starts, weekly, strict=True)],
        "salary": {
            "currency": "BDT",
            "period": "month",
            "samples": len(all_pay),
            "median": round(median(all_pay)) if len(all_pay) >= MIN_SALARY_SAMPLES else None,
            "by_discipline": [
                {"key": key, "median": round(median(values)), "samples": len(values)}
                for key, values in sorted(salaries.items()) if len(values) >= MIN_SALARY_SAMPLES
            ],
        },
        "latest": [job_to_dict(j) for j in latest],
    }
