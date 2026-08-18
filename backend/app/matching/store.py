"""Anonymized event log powering the retraining flywheel.

Only what /api/jobs/search already receives is stored: extracted skills,
title, and years of experience, plus which job it matched against. Never
raw resume text, name, email, or phone — those never reach this module.
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
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
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
