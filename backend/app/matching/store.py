"""Anonymized event log powering the retraining flywheel.

Two tables:
- match_events: logged from /api/jobs/search — skills/title/years plus
  which job it matched against.
- resume_scans: logged from /api/analyze — skills/title/years plus the
  resulting ATS scores, one row per scan, independent of whether the user
  went on to search jobs.

Never raw resume text, name, email, or phone — those never reach this
module in either case.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "events.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_title TEXT,
    skills TEXT NOT NULL,
    years_experience REAL,
    job_title TEXT NOT NULL,
    job_company TEXT,
    job_source TEXT,
    relevance_score REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resume_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    skills TEXT NOT NULL,
    years_experience REAL,
    ats_score REAL,
    formatting_score REAL,
    content_score REAL,
    keyword_score REAL,
    had_job_description INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_event(
    resume_title: str | None,
    skills: list[str],
    years_experience: float | None,
    job_title: str,
    job_company: str,
    job_source: str,
    relevance_score: float,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO match_events "
            "(resume_title, skills, years_experience, job_title, job_company, job_source, "
            "relevance_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                resume_title,
                json.dumps(skills),
                years_experience,
                job_title,
                job_company,
                job_source,
                relevance_score,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def fetch_events(limit: int = 5000) -> list[dict]:
    if not DB_PATH.exists():
        return []
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM match_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "resume_title": row["resume_title"],
            "skills": json.loads(row["skills"]),
            "years_experience": row["years_experience"],
            "job_title": row["job_title"],
            "job_company": row["job_company"],
            "job_source": row["job_source"],
            "relevance_score": row["relevance_score"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def event_count() -> int:
    if not DB_PATH.exists():
        return 0
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM match_events").fetchone()[0]


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
    with _connect() as conn:
        conn.execute(
            "INSERT INTO resume_scans "
            "(title, skills, years_experience, ats_score, formatting_score, content_score, "
            "keyword_score, had_job_description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title,
                json.dumps(skills),
                years_experience,
                ats_score,
                formatting_score,
                content_score,
                keyword_score,
                int(had_job_description),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def fetch_resume_scans(limit: int = 5000) -> list[dict]:
    if not DB_PATH.exists():
        return []
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM resume_scans ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "title": row["title"],
            "skills": json.loads(row["skills"]),
            "years_experience": row["years_experience"],
            "ats_score": row["ats_score"],
            "formatting_score": row["formatting_score"],
            "content_score": row["content_score"],
            "keyword_score": row["keyword_score"],
            "had_job_description": bool(row["had_job_description"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def resume_scan_count() -> int:
    if not DB_PATH.exists():
        return 0
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM resume_scans").fetchone()[0]
