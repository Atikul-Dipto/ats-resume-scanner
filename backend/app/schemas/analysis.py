from pydantic import BaseModel

from app.schemas.resume import ResumeDocument


class FormattingIssue(BaseModel):
    severity: str  # "critical" | "warning" | "info"
    message: str
    location: str | None = None


class FlaggedLine(BaseModel):
    text: str
    reasons: list[str]


class SectionCheck(BaseModel):
    name: str
    found: bool


class KeywordMatch(BaseModel):
    matched: list[str]
    missing: list[str]
    match_score: float  # 0-100, only meaningful when a job description was supplied


class ExtractedProfile(BaseModel):
    emails: list[str]
    phones: list[str]
    links: list[str]
    skills: list[str]
    years_experience: float | None
    current_title: str | None


class AnalyzeResponse(BaseModel):
    ats_score: float  # 0-100 overall
    formatting_score: float
    content_score: float
    keyword_score: float
    formatting_issues: list[FormattingIssue]
    sections: list[SectionCheck]
    keywords: KeywordMatch
    profile: ExtractedProfile
    suggestions: list[str]
    flagged_lines: list[FlaggedLine]


class JobListing(BaseModel):
    title: str
    company: str
    location: str | None
    url: str
    source: str
    relevance_score: float
    is_worldwide_remote: bool


class JobSearchResponse(BaseModel):
    query: str
    results: list[JobListing]


class BuilderAnalysisResponse(AnalyzeResponse):
    """Live score for a resume being edited in the builder."""


class UploadAnalysisResponse(AnalyzeResponse):
    # Best-effort structured version of the upload, so the user can open it
    # in the builder instead of retyping. Heuristic — the UI asks for review.
    draft_document: ResumeDocument
