"""Request/response bodies for the auth, resume and builder endpoints."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.resume import ResumeDocument

JobDescription = Annotated[str, StringConstraints(max_length=20_000)]


class Credentials(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    created_at: datetime
    is_admin: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ResumeCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    document: ResumeDocument = Field(default_factory=ResumeDocument)
    target_job_description: JobDescription | None = None


class ResumeUpdate(ResumeCreate):
    version: int


class ResumeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    version: int
    last_score: float | None
    created_at: datetime
    updated_at: datetime


class ResumeOut(ResumeSummary):
    document: ResumeDocument
    target_job_description: str | None


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resume_id: str | None
    source: str
    filename: str | None
    ats_score: float
    formatting_score: float
    content_score: float
    keyword_score: float
    had_job_description: bool
    created_at: datetime


class BuilderScoreRequest(BaseModel):
    document: ResumeDocument
    job_description: JobDescription | None = None


class ExportRequest(BaseModel):
    document: ResumeDocument
    filename: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
