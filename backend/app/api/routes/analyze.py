import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.analysis.pipeline import analyze_parsed
from app.api.deps import OptionalUser
from app.builder.importer import document_from_text
from app.core.config import get_settings
from app.core.executor import run_cpu_bound
from app.core.rate_limit import rate_limit
from app.db.scans import record_scan
from app.matching.store import log_analysis
from app.parsers import DocumentTooLarge, UnsupportedDocument, parse_upload
from app.schemas.analysis import UploadAnalysisResponse

router = APIRouter(prefix="/api", tags=["scan"])
logger = logging.getLogger(__name__)


def _analyze_upload(filename: str, contents: bytes, max_pages: int, job_description: str | None) -> dict:
    parsed = parse_upload(filename, contents, max_pages=max_pages)
    if not parsed["text"].strip():
        raise HTTPException(422, "No text could be extracted — this may be a scanned image. Export a text-based PDF or .docx.")
    result = analyze_parsed(parsed, job_description)
    result["draft_document"] = document_from_text(parsed["text"])
    return result


@router.post(
    "/analyze",
    response_model=UploadAnalysisResponse,
    dependencies=[Depends(rate_limit("analyze"))],
)
async def analyze_resume(
    background: BackgroundTasks,
    user: OptionalUser,
    file: Annotated[UploadFile, File()],
    job_description: Annotated[str | None, Form(max_length=20_000)] = None,
):
    settings = get_settings()
    filename = file.filename or ""
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only .pdf and .docx files are supported.")

    # Read one byte past the limit: enough to know it's too big without
    # buffering an arbitrarily large body into memory.
    contents = await file.read(settings.max_upload_bytes + 1)
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb}MB limit.")

    try:
        result = await run_cpu_bound(
            _analyze_upload, filename, contents, settings.max_pdf_pages, job_description
        )
    except HTTPException:
        raise
    except UnsupportedDocument as exc:
        raise HTTPException(400, str(exc)) from exc
    except DocumentTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    except Exception as exc:
        logger.warning("Failed to parse upload %r: %s", filename, exc)
        raise HTTPException(422, "Could not parse this file. It may be corrupted or password-protected.") from exc

    has_jd = bool(job_description and job_description.strip())
    if settings.events_enabled:
        background.add_task(log_analysis, result, has_jd)
    if user is not None:
        background.add_task(record_scan, user.id, result, source="upload",
                            had_job_description=has_jd, filename=filename)
    return result
