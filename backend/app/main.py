"""App factory. Routes live in app/api/routes; this file only wires them up."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, analyze, auth, builder, health, jobs, resumes
from app.core import executor
from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.matching.infer import get_encoder

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One pooled HTTP client for the process, instead of a new connection
    # pool (and TLS handshakes) per job search.
    app.state.http = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        headers={"User-Agent": "ats-resume-builder/2.0 (+https://github.com/Atikul-Dipto/ats-resume-scanner)"},
    )
    executor.reset()
    # Load the matching encoder now rather than inside the first user's request.
    if get_encoder() is None:
        logger.warning("Matching encoder artifacts not found; job search will use keyword ranking only.")
    yield
    await app.state.http.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title="ATS Resume Builder API", version="2.0.0", lifespan=lifespan)

    # Order matters: CORS is added last so it's the outermost layer and even
    # error responses produced inside RequestContextMiddleware get CORS headers
    # (otherwise the browser reports a 500 as an opaque CORS failure).
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        # Bearer tokens, not cookies — no credentials mode needed.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"],
        max_age=600,
    )

    for module in (health, auth, analyze, builder, resumes, jobs, admin):
        app.include_router(module.router)
    return app


app = create_app()
