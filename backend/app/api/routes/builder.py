"""Stateless builder endpoints — no account needed. The document travels in
the request body, so anonymous users get live scoring and export too."""

import re
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.analysis.pipeline import analyze_document
from app.builder.export_docx import render_docx
from app.builder.export_latex import render_latex
from app.builder.export_pdf import render_pdf
from app.core.executor import run_cpu_bound
from app.core.rate_limit import rate_limit
from app.schemas.analysis import BuilderAnalysisResponse
from app.schemas.api import BuilderScoreRequest, ExportRequest

router = APIRouter(prefix="/api/builder", tags=["builder"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
RENDERERS = {"pdf": render_pdf, "docx": render_docx, "tex": render_latex}


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned[:80] or "resume"


@router.post("/score", response_model=BuilderAnalysisResponse, dependencies=[Depends(rate_limit("builder"))])
async def score_document(body: BuilderScoreRequest):
    return await run_cpu_bound(analyze_document, body.document, body.job_description)


@router.post("/export/{fmt}", dependencies=[Depends(rate_limit("export"))])
async def export_document(fmt: Literal["pdf", "docx", "tex"], body: ExportRequest) -> Response:
    data = await run_cpu_bound(RENDERERS[fmt], body.document)
    name = safe_filename(body.filename or f"{body.document.basics.name} Resume")
    return Response(
        content=data,
        media_type=MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'},
    )
