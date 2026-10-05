"""The single analysis entry point for both product surfaces.

- analyze_parsed(): an uploaded file, after parsing. Formatting issues come
  from the file's structure; the profile is regex-extracted from its text.
- analyze_document(): a resume being edited in the builder. The layout is
  ATS-safe by construction, so "formatting" becomes structural completeness
  checks instead, and the profile is read straight from the structured data.

Both feed the same scorer, so a resume built here and then exported and
uploaded scores the same as it did in the editor.
"""

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
from app.builder.checks import check_document
from app.builder.layout import render_text
from app.schemas.resume import ResumeDocument


def _analyze(text: str, formatting_issues: list[dict], job_description: str | None, profile: dict) -> dict:
    has_jd = bool(job_description and job_description.strip())
    sections = detect_sections(text)
    keyword_result = match_keywords(text, job_description)
    scores = score_resume(text, sections, formatting_issues, keyword_result, has_jd)
    return {
        **scores,
        "formatting_issues": formatting_issues,
        "sections": sections,
        "keywords": keyword_result,
        "profile": profile,
        "flagged_lines": find_weak_bullets(text),
    }


def extract_profile(text: str) -> dict:
    return {
        "emails": extract_emails(text),
        "phones": extract_phones(text),
        "links": extract_links(text),
        "skills": extract_skills(text),
        "years_experience": extract_years_experience(text),
        "current_title": extract_current_title(text),
    }


def analyze_parsed(parsed: dict, job_description: str | None) -> dict:
    text = parsed["text"]
    return _analyze(text, check_formatting(parsed), job_description, extract_profile(text))


def analyze_document(doc: ResumeDocument, job_description: str | None) -> dict:
    text = render_text(doc)
    basics = doc.basics
    current = next((e for e in doc.experience if e.title), None)
    # Structured skills the user typed, plus any known skills mentioned in
    # their bullets — same vocabulary the job search ranks against.
    skills = list(dict.fromkeys([s.lower() for s in doc.all_skills()] + extract_skills(text)))
    profile = {
        "emails": [basics.email] if basics.email else [],
        "phones": [basics.phone] if basics.phone else [],
        "links": [link.url for link in basics.links],
        "skills": skills,
        "years_experience": extract_years_experience(text),
        "current_title": (current.title if current else None) or basics.headline or None,
    }
    return _analyze(text, check_document(doc), job_description, profile)
