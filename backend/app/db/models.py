"""Relational schema. Migrations live in backend/alembic/versions — change a
model here, then `alembic revision --autogenerate -m "..."` and review it.

Two kinds of data, deliberately separated:
- Account data (users, resumes, scans): owned by a user, deleted with them.
- Anonymized events (resume_scan_events, match_events): title + skills +
  scores only, never linked to a user, never raw resume text or contact info.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    document: Mapped[dict] = mapped_column(JSONType)
    target_job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optimistic concurrency: a PUT must send the version it edited, so two
    # open tabs can't silently overwrite each other.
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="resumes")


class Scan(Base):
    """Score history for signed-in users: one row per upload scan or resume save."""

    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    resume_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source: Mapped[str] = mapped_column(String(20))  # "upload" | "builder"
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats_score: Mapped[float] = mapped_column(Float)
    formatting_score: Mapped[float] = mapped_column(Float)
    content_score: Mapped[float] = mapped_column(Float)
    keyword_score: Mapped[float] = mapped_column(Float)
    had_job_description: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ResumeScanEvent(Base):
    __tablename__ = "resume_scan_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    skills: Mapped[list] = mapped_column(JSONType)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    ats_score: Mapped[float] = mapped_column(Float)
    formatting_score: Mapped[float] = mapped_column(Float)
    content_score: Mapped[float] = mapped_column(Float)
    keyword_score: Mapped[float] = mapped_column(Float)
    had_job_description: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resume_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    skills: Mapped[list] = mapped_column(JSONType)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    job_title: Mapped[str] = mapped_column(String(300))
    job_company: Mapped[str | None] = mapped_column(String(300), nullable=True)
    job_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
