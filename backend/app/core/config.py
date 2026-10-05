"""All runtime configuration, env-driven. One place to look for every knob.

Every value has a default that works for local development with zero setup
(SQLite file, in-memory cache). Production overrides come from environment
variables — see backend/.env.example for the full list.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-insecure-secret-change-me-before-deploying"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Storage. Any SQLAlchemy URL; postgres:// and postgresql:// are rewritten
    # to the psycopg3 driver so a Neon/Supabase/Render connection string can
    # be pasted in unchanged.
    database_url: str = "sqlite:///./data/app.db"
    # Optional. Unset = per-process in-memory cache and rate limits, which is
    # correct for a single instance. Set it before running >1 API instance.
    redis_url: str | None = None

    # Auth. Leave JWT_SECRET unset to have the app generate a random secret
    # and keep it in the database (see core/security.py) — secure with zero
    # configuration, and it lives exactly as long as the accounts it signs for.
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7
    max_resumes_per_user: int = 25
    # Comma-separated emails with admin rights (post and edit job listings).
    # Env-only on purpose: nobody can grant themselves admin through the API.
    admin_emails: str = ""

    # HTTP
    allowed_origins: str = "http://localhost:5173"

    # Upload / parsing limits. These bound the CPU and memory a single
    # request can consume, which is what keeps one instance healthy under load.
    max_upload_mb: int = 5
    max_pdf_pages: int = 10
    parse_concurrency: int = 4

    # Rate limits, "<count>/<second|minute|hour>", per client IP.
    rate_limit_analyze: str = "12/minute"
    rate_limit_builder: str = "90/minute"
    rate_limit_export: str = "20/minute"
    rate_limit_jobs: str = "20/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_match: str = "30/minute"

    # Job search
    jobs_cache_ttl_seconds: int = 900
    jobs_search_timeout_seconds: float = 12.0
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "us"

    # Job board: remote engineering/data jobs pulled from the public APIs into
    # the catalog. Sync runs in the background when the catalog is read and
    # the last sync is older than the interval (or via `python -m app.jobs.sync`).
    jobs_sync_enabled: bool = True
    jobs_sync_interval_hours: float = 6.0
    jobs_external_max_age_days: int = 30
    jobs_match_candidates: int = 2000

    # Anonymized usage logging for retraining the matching encoder.
    events_enabled: bool = True

    # Render sets RENDER=true. Its free tier has an ephemeral filesystem, so a
    # SQLite database there is wiped on every restart — reported by /api/meta.
    render: bool = False

    # Directory holding DejaVuSans*.ttf for Unicode PDF export. Auto-detected
    # on Debian/Ubuntu (fonts-dejavu-core); falls back to core PDF fonts.
    pdf_font_dir: str | None = None

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def admin_emails_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def jwt_secret_configured(self) -> bool:
        return self.jwt_secret != DEV_JWT_SECRET

    @property
    def persistent_storage(self) -> bool:
        """False when data won't survive a restart (SQLite on an ephemeral host)."""
        on_ephemeral_host = self.render or self.environment == "production"
        return not (self.sqlalchemy_url.startswith("sqlite") and on_ephemeral_host)

    @model_validator(mode="after")
    def _refuse_weak_secret(self):
        # An unset secret is fine (a random one is generated and stored);
        # an explicitly configured weak one is a mistake worth failing on.
        if self.environment == "production" and self.jwt_secret_configured and len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be a random value of 32+ characters (or leave it unset).")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
