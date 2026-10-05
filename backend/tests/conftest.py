"""Test harness.

Every test gets an isolated, fully migrated database: SQLite by default (a
copy of a template migrated once with Alembic, so migrations themselves are
exercised), or real Postgres when TEST_DATABASE_URL is set (CI does this) —
then tables are truncated between tests instead.
"""

import os
import shutil
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
# Tests trigger catalog syncs explicitly; never hit real job APIs in the background.
os.environ["JOBS_SYNC_ENABLED"] = "false"
for scope in ("analyze", "builder", "export", "jobs", "auth", "match", "assistant"):
    os.environ[f"RATE_LIMIT_{scope.upper()}"] = "10000/minute"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.cache import MemoryCache, set_cache  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import reset_engine  # noqa: E402
from app.jobs.matcher import reset_index  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("TEST_DATABASE_URL")


def _migrate(url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    if PG_URL:
        url = Settings(database_url=PG_URL).sqlalchemy_url
        _migrate(url)
        return url
    path = tmp_path_factory.mktemp("db") / "template.db"
    _migrate(f"sqlite:///{path}")
    return path


def _truncate_all(url: str) -> None:
    engine = create_engine(url)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture(autouse=True)
def database(_template_db, tmp_path, monkeypatch):
    if PG_URL:
        _truncate_all(_template_db)
        url = _template_db
    else:
        db_file = tmp_path / "test.db"
        shutil.copy(_template_db, db_file)
        url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    reset_engine()
    set_cache(MemoryCache())
    reset_index()
    yield url
    reset_engine()
    set_cache(None)
    get_settings.cache_clear()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register(client):
    """Registers a user and returns auth headers for them."""

    def _register(email: str = "jane@example.com", password: str = "correct-horse-battery") -> dict:
        resp = client.post("/api/auth/register", json={"email": email, "password": password})
        assert resp.status_code == 201, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _register


SAMPLE_DOCUMENT = {
    "basics": {
        "name": "Jane Doe",
        "headline": "Data Analyst",
        "email": "jane@example.com",
        "phone": "+1 415-555-0182",
        "location": "Dhaka, Bangladesh",
        "links": [{"url": "linkedin.com/in/janedoe"}],
        "summary": "Data analyst with 4 years of experience turning operational data into dashboards and decisions.",
    },
    "experience": [
        {
            "title": "Data Analyst",
            "company": "Acme Corp",
            "location": "Dhaka",
            "start": "2020-01",
            "current": True,
            "bullets": [
                "Built ETL pipelines with Python and Airflow, reducing report latency by 40%.",
                "Led migration of 30 dashboards to Power BI, saving 10 hours per week.",
            ],
        },
        {
            "title": "Junior Analyst",
            "company": "Beta Ltd",
            "start": "2018-06",
            "end": "2019-12",
            "bullets": [
                "Automated weekly sales reporting in SQL, cutting turnaround from 2 days to 2 hours.",
                "Reduced data-entry errors by 25% by building validation checks in Excel.",
            ],
        },
    ],
    "education": [
        {"institution": "State University", "degree": "BSc Computer Science", "start": "2014", "end": "2018",
         "details": ["GPA 3.8/4.0"]},
    ],
    "skills": [
        {"name": "Languages", "skills": ["Python", "SQL"]},
        {"name": "Tools", "skills": ["Power BI", "Tableau", "Airflow", "Pandas"]},
    ],
    "certifications": [{"name": "Google Data Analytics", "issuer": "Google", "date": "2022-05"}],
}


@pytest.fixture
def sample_document() -> dict:
    import copy

    return copy.deepcopy(SAMPLE_DOCUMENT)
