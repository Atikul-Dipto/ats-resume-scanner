"""Request IDs + one structured log line per request.

Every response carries X-Request-ID (honoring an incoming one from a proxy),
and every log line for that request includes it, so a user-reported error
can be traced to its logs across instances.
"""

import contextvars
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    ))
    root = logging.getLogger("app")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False


logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 64 else uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Answer here rather than letting Starlette's outermost error
            # handler do it, so the 500 still passes through CORS and carries
            # the request id the user can report.
            logger.exception("%s %s failed", request.method, request.url.path)
            response = JSONResponse(
                {"detail": "Something went wrong on our side. Please try again.", "request_id": request_id},
                status_code=500,
            )
        finally:
            request_id_var.reset(token)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        if request.url.path not in ("/api/health",):
            logger.info(
                "%s %s -> %s in %.0fms", request.method, request.url.path, response.status_code, elapsed_ms,
                extra={"request_id": request_id},
            )
        return response
