import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.ats_scorer import score_resume
from app.analysis.content_flags import find_weak_bullets
from app.analysis.formatting_checker import check_formatting
from app.analysis.keyword_matcher import match_keywords
from app.analysis.profile_extractor import (
    extract_current_title,
    extract_emails,
    extract_links,
    extract_phones,
    extract_skills,
    extract_years_experience,
)
from app.analysis.section_detector import detect_sections
from app.jobs.aggregator import search_jobs
from app.matching.store import event_count, log_event, log_resume_scan, resume_scan_count
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf

app = FastAPI(title="ATS Resume Scanner API")

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def stats():
    """Aggregate counts only — no per-scan or per-search detail exposed here."""
    return {
        "resume_scans": resume_scan_count(),
        "job_search_events": event_count(),
    }


@app.post("/api/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str | None = Form(default=None),
):
    filename = (file.filename or "").lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        raise HTTPException(400, "Only .pdf and .docx files are supported.")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File exceeds 5MB limit.")

    try:
        parsed = parse_pdf(contents) if filename.endswith(".pdf") else parse_docx(contents)
    except Exception:
        raise HTTPException(422, "Could not parse this file. It may be corrupted or password-protected.")

    text = parsed["text"]
    if not text.strip():
        raise HTTPException(422, "No text could be extracted from this file.")

    sections = detect_sections(text)
    formatting_issues = check_formatting(parsed)
    keyword_result = match_keywords(text, job_description)
    scores = score_resume(text, sections, formatting_issues, keyword_result, bool(job_description))
    flagged_lines = find_weak_bullets(text)

    profile = {
        "emails": extract_emails(text),
        "phones": extract_phones(text),
        "links": extract_links(text),
        "skills": extract_skills(text),
        "years_experience": extract_years_experience(text),
        "current_title": extract_current_title(text),
    }

    # Best-effort: anonymized flywheel data for retraining the matching
    # encoder (see app/matching/train.py). Never let logging failures
    # affect the actual analysis response.
    try:
        log_resume_scan(
            title=profile["current_title"],
            skills=profile["skills"],
            years_experience=profile["years_experience"],
            ats_score=scores["ats_score"],
            formatting_score=scores["formatting_score"],
            content_score=scores["content_score"],
            keyword_score=scores["keyword_score"],
            had_job_description=bool(job_description),
        )
    except Exception:
        pass

    return {
        **scores,
        "formatting_issues": formatting_issues,
        "sections": sections,
        "keywords": keyword_result,
        "profile": profile,
        "flagged_lines": flagged_lines,
    }


@app.post("/api/jobs/search")
async def jobs_search(
    query: str = Form(...),
    skills: str = Form(default=""),
    location: str = Form(default=""),
):
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    results = await search_jobs(query, skill_list, location)

    # Best-effort: this is the anonymized flywheel data used to retrain the
    # matching encoder later (see app/matching/train.py). Never let logging
    # failures affect the actual search response.
    try:
        for job in results[:3]:
            log_event(
                resume_title=query,
                skills=skill_list,
                years_experience=None,
                job_title=job["title"],
                job_company=job["company"],
                job_source=job["source"],
                relevance_score=job["relevance_score"],
            )
    except Exception:
        pass

    return {"query": query, "results": results}
