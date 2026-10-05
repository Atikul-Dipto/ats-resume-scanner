"""Contracts for the job board: listings, admin editing, and resume matching."""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.jobs.taxonomy import DISCIPLINES
from app.schemas.resume import ResumeDocument

Discipline = Literal["data", "software", "civil", "electrical", "mechanical"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship"]
Workplace = Literal["onsite", "remote", "hybrid"]
JobStatus = Literal["draft", "published", "closed"]

# Apply links are rendered as hrefs: only allow schemes that can't run script.
SAFE_URL_RE = re.compile(r"^(https?://[^\s<>\"']+|mailto:[^\s<>\"']+@[^\s<>\"']+)$", re.IGNORECASE)


def is_safe_url(url: str) -> bool:
    return bool(SAFE_URL_RE.match(url))


class JobIn(BaseModel):
    """What an admin submits when posting or editing a listing."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
    company: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    discipline: Discipline
    employment_type: EmploymentType = "full_time"
    workplace: Workplace = "onsite"
    experience_min: Annotated[float, Field(ge=0, le=50)] | None = None
    experience_max: Annotated[float, Field(ge=0, le=50)] | None = None
    salary_min: Annotated[int, Field(ge=0, le=100_000_000)] | None = None
    salary_max: Annotated[int, Field(ge=0, le=100_000_000)] | None = None
    salary_currency: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")] = "BDT"
    salary_period: Literal["month", "year"] = "month"
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=20_000)]
    skills: Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]],
                      Field(max_length=40)] = []
    apply_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    deadline: date | None = None
    status: JobStatus = "published"

    @field_validator("apply_url")
    @classmethod
    def _safe_apply_url(cls, value: str) -> str:
        if value and not is_safe_url(value):
            raise ValueError("Apply link must be an http(s):// URL or a mailto: address.")
        return value

    @model_validator(mode="after")
    def _ranges(self):
        if self.experience_min is not None and self.experience_max is not None and self.experience_min > self.experience_max:
            raise ValueError("Minimum experience can't exceed maximum experience.")
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("Minimum salary can't exceed maximum salary.")
        return self


class JobSummary(BaseModel):
    """Built with app.jobs.catalog.job_to_dict (which also derives `snippet`)."""

    id: str
    source: str
    title: str
    company: str
    location: str
    discipline: Discipline
    employment_type: str
    workplace: str
    experience_min: float | None
    experience_max: float | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    salary_period: str
    skills: list[str]
    apply_url: str
    deadline: date | None
    status: str
    created_at: datetime
    snippet: str = ""


class JobOut(JobSummary):
    description: str
    updated_at: datetime


class JobListOut(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int
    facets: dict[str, int]  # open listings per discipline, for the filter chips
    disciplines: dict[str, str] = Field(default_factory=lambda: dict(DISCIPLINES))


class JobStatusIn(BaseModel):
    status: JobStatus


class MatchRequest(BaseModel):
    document: ResumeDocument
    discipline: Discipline | None = None
    workplace: Workplace | None = None
    source: Literal["local", "remote"] | None = None
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class MatchComponents(BaseModel):
    skills: float | None
    text: float
    semantic: float | None
    experience: float


class JobMatch(BaseModel):
    job: JobSummary
    match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    experience_note: str | None
    components: MatchComponents


class MatchProfile(BaseModel):
    title: str | None
    years_experience: float | None
    skills: list[str]
    detected_discipline: Discipline | None


class MatchOut(BaseModel):
    profile: MatchProfile
    total_considered: int
    results: list[JobMatch]
