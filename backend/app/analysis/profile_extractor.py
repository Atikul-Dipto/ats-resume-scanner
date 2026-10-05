import re
from datetime import datetime

from app.analysis.skills_data import SKILLS

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}")
LINK_RE = re.compile(r"(https?://[^\s,]+|(?:linkedin\.com|github\.com)[^\s,]*)", re.IGNORECASE)
YEAR_RANGE_RE = re.compile(
    r"(\d{4})\s*(?:-|–|to)\s*(present|current|\d{4})", re.IGNORECASE
)
TITLE_LINE_RE = re.compile(
    r"^(?:senior |junior |lead |principal |staff )?"
    r"(?:software|data|product|project|business|financial|marketing|sales|operations|"
    r"supply chain|hr|frontend|backend|full[- ]stack|devops|qa|research|graphic|ux|ui)"
    r"\s+(?:engineer|analyst|manager|scientist|developer|designer|specialist|consultant|"
    r"associate|director|coordinator|intern)",
    re.IGNORECASE,
)
EXPERIENCE_HEADING_RE = re.compile(
    r"^\s*(experience|work experience|employment history|work history)\s*$", re.IGNORECASE
)
NEXT_HEADING_RE = re.compile(
    r"^\s*(education|academic background|skills|technical skills|core competencies|"
    r"projects|certifications|awards)\s*$",
    re.IGNORECASE,
)


def _experience_section_text(text: str) -> str | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if EXPERIENCE_HEADING_RE.match(line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start, len(lines)):
        if NEXT_HEADING_RE.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def extract_emails(text: str) -> list[str]:
    return sorted(set(EMAIL_RE.findall(text)))


def extract_phones(text: str) -> list[str]:
    candidates = PHONE_RE.findall(text)
    return sorted({c.strip() for c in candidates if len(re.sub(r"\D", "", c)) >= 7})


def extract_links(text: str) -> list[str]:
    return sorted(set(LINK_RE.findall(text)))


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.append(skill)
    return found


def extract_years_experience(text: str) -> float | None:
    scope = _experience_section_text(text) or text
    ranges = YEAR_RANGE_RE.findall(scope)
    if not ranges:
        return None
    current_year = datetime.now().year
    spans = []
    for start, end in ranges:
        start_year = int(start)
        end_year = current_year if end.lower() in ("present", "current") else int(end)
        if end_year >= start_year:
            spans.append((start_year, end_year))
    if not spans:
        return None
    # Merge overlapping ranges so concurrent roles aren't double-counted, then sum.
    spans.sort()
    merged = [spans[0]]
    for start_year, end_year in spans[1:]:
        last_start, last_end = merged[-1]
        if start_year <= last_end:
            merged[-1] = (last_start, max(last_end, end_year))
        else:
            merged.append((start_year, end_year))
    return float(sum(end - start for start, end in merged))


def extract_current_title(text: str) -> str | None:
    scope = _experience_section_text(text) or text
    for line in scope.splitlines():
        stripped = line.strip()
        word_count = len(stripped.split())
        if 3 < len(stripped) < 60 and not stripped.endswith(".") and word_count <= 8:
            match = TITLE_LINE_RE.search(stripped)
            if match:
                # Just the title — the rest of the line is usually the employer,
                # which shouldn't seed job searches or reach the anonymized log.
                return match.group(0)
    return None
