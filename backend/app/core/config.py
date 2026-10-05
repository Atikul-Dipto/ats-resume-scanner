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

    # Auth
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7
    max_resumes_per_user: int = 25

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

    # Job search
    jobs_cache_ttl_seconds: int = 900
    jobs_search_timeout_seconds: float = 12.0
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "us"

    # Anonymized usage logging for retraining the matching encoder.
    events_enabled: bool = True

    # Directory holding DejaVuSans*.ttf for Unicode PDF export. Auto-detected
    # on Debian/Ubuntu (fonts-dejavu-core); falls back to core PDF fonts.
    pdf_font_dir: str | None = None

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

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

    @model_validator(mode="after")
    def _refuse_insecure_production(self):
        if self.environment == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be set to a random value of 32+ characters in production.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
