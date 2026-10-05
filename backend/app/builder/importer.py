"""Best-effort conversion of an uploaded resume's text into a ResumeDocument,
so "scan my resume" can flow straight into "fix it in the builder".

Heuristic by nature — resumes have no standard structure — so the goal is a
draft that saves most of the retyping, not a perfect parse. The UI tells the
user to review every field. Output is always clamped to the schema's limits,
so a messy PDF can never produce an invalid document.
"""

import re

from app.analysis.ats_scorer import BULLET_LINE_RE
from app.analysis.profile_extractor import extract_emails, extract_links, extract_phones
from app.schemas.resume import (
    Basics,
    CertificationItem,
    EducationItem,
    ExperienceItem,
    Link,
    ProjectItem,
    ResumeDocument,
    SkillGroup,
)

HEADINGS = {
    "summary": {"summary", "professional summary", "profile", "professional profile", "objective",
                "career objective", "about", "about me", "career summary"},
    "experience": {"experience", "work experience", "professional experience", "employment history",
                   "work history", "employment", "relevant experience", "career history"},
    "education": {"education", "academic background", "education & training", "education and training",
                  "academic qualifications", "qualifications"},
    "skills": {"skills", "technical skills", "core competencies", "key skills", "skills & tools",
               "skills and tools", "competencies", "tools", "technologies", "tech stack"},
    "projects": {"projects", "personal projects", "key projects", "selected projects", "academic projects"},
    "certifications": {"certifications", "licenses & certifications", "licenses and certifications",
                       "certificates", "certification", "courses", "training"},
}
_HEADING_LOOKUP = {alias: section for section, aliases in HEADINGS.items() for alias in aliases}

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE = (
    r"(?:(?:(?P<{p}m>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)|(?P<{p}n>\d{{1,2}})/)?"
    r"(?P<{p}y>(?:19|20)\d{{2}})"
)
RANGE_RE = re.compile(
    _DATE.format(p="s") + r"\s*(?:-|–|—|to)\s*(?:(?P<present>present|current|now)|" + _DATE.format(p="e") + ")",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

TITLE_WORDS = re.compile(
    r"\b(analyst|engineer|manager|developer|designer|intern|consultant|specialist|lead|director|"
    r"officer|associate|coordinator|scientist|executive|assistant|head|architect|administrator|"
    r"representative|accountant|teacher|researcher|supervisor|founder|owner|technician|writer)\b",
    re.IGNORECASE,
)
DEGREE_WORDS = re.compile(
    r"\b(bachelor|master|b\.?sc|m\.?sc|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?|bba|mba|ph\.?d|diploma|degree|"
    r"hsc|ssc|a-levels?|o-levels?|associate of|certificate in)\b",
    re.IGNORECASE,
)
SCHOOL_WORDS = re.compile(
    r"\b(university|college|institute|school|academy|polytechnic|conservatory)\b", re.IGNORECASE
)
SINGLE_DATE_RE = re.compile(
    r"(?:(?P<m>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(?P<y>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
SPLIT_RE = re.compile(r"\s+(?:at|@)\s+|\s*[|—–]\s*|\s+-\s+|,\s+")
CONTACT_SPLIT_RE = re.compile(r"\s*[|•·;]\s*")
SKILL_SPLIT_RE = re.compile(r"\s*[,|•·;]\s*")


def _clip(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def _heading(line: str) -> str | None:
    cleaned = line.strip().rstrip(":").strip().lower()
    if not cleaned or len(cleaned) > 40:
        return None
    return _HEADING_LOOKUP.get(cleaned)


def _bullet(line: str) -> str | None:
    match = BULLET_LINE_RE.match(line)
    return match.group(1).strip() if match else None


def _to_date(month: str | None, numeric_month: str | None, year: str | None) -> str:
    if not year:
        return ""
    if month:
        return f"{year}-{_MONTHS[month.lower()[:3]]:02d}"
    if numeric_month and 1 <= int(numeric_month) <= 12:
        return f"{year}-{int(numeric_month):02d}"
    return year


def _parse_range(line: str):
    """Returns (start, end, current, line_without_dates) or None."""
    match = RANGE_RE.search(line)
    if not match:
        return None
    start = _to_date(match.group("sm"), match.group("sn"), match.group("sy"))
    current = bool(match.group("present"))
    end = "" if current else _to_date(match.group("em"), match.group("en"), match.group("ey"))
    rest = (line[: match.start()] + " " + line[match.end():]).strip(" |,–—-·\t")
    return start, end, current, rest


def _split_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        section = _heading(line)
        if section:
            current = section
            sections.setdefault(section, [])
            continue
        (sections[current] if current else header).append(line)
    return header, sections


def _is_continuation(line: str, previous_bullet: str | None) -> bool:
    """PDF text extraction breaks long bullets across lines; glue them back."""
    if previous_bullet is None or RANGE_RE.search(line):
        return False
    return line[:1].islower() or not previous_bullet.rstrip().endswith((".", "!", "?"))


def _split_title_company(text: str) -> tuple[str, str]:
    if re.search(r"\s+(?:at|@)\s+", text):
        title, company = re.split(r"\s+(?:at|@)\s+", text, maxsplit=1)
        return title, company
    parts = [p for p in SPLIT_RE.split(text) if p.strip()]
    if len(parts) < 2:
        return text, ""
    if TITLE_WORDS.search(parts[1]) and not TITLE_WORDS.search(parts[0]):
        return parts[1], parts[0]
    return parts[0], parts[1]


def _parse_experience(lines: list[str]) -> list[ExperienceItem]:
    entries: list[dict] = []
    last_bullet: str | None = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        bullet = _bullet(line)
        if bullet is not None:
            if not entries:
                entries.append({"bullets": []})
            entries[-1]["bullets"].append(bullet)
            last_bullet = bullet
            continue
        if _is_continuation(line, last_bullet) and entries and entries[-1]["bullets"]:
            entries[-1]["bullets"][-1] += " " + line
            last_bullet = entries[-1]["bullets"][-1]
            continue

        last_bullet = None
        if not entries or entries[-1]["bullets"]:
            entries.append({"bullets": []})
        entry = entries[-1]

        parsed = _parse_range(line)
        if parsed:
            entry["start"], entry["end"], entry["current"], line = parsed
        if not line:
            continue
        if "title" not in entry:
            entry["title"], company = _split_title_company(line)
            if company:
                entry["company"] = company
        elif "company" not in entry:
            entry["company"] = line
        elif "location" not in entry and len(line) < 60:
            entry["location"] = line

    return [
        ExperienceItem(
            title=_clip(e.get("title", "")),
            company=_clip(e.get("company", "")),
            location=_clip(e.get("location", "")),
            start=e.get("start", ""),
            end=e.get("end", ""),
            current=e.get("current", False),
            bullets=[_clip(b, 500) for b in e["bullets"]][:15],
        )
        for e in entries
        if e.get("title") or e.get("company") or e["bullets"]
    ][:20]


def _parse_education(lines: list[str]) -> list[EducationItem]:
    entries: list[dict] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        text = _bullet(line) or line
        start = end = ""
        parsed = _parse_range(text)
        if parsed:
            start, end, _, text = parsed
        elif (years := YEAR_RE.findall(text)) and len(YEAR_RE.sub("", text).strip(" ()|,–—-")) == 0:
            end, text = years[-1], ""

        is_degree = bool(DEGREE_WORDS.search(text))
        is_school = bool(SCHOOL_WORDS.search(text))
        current = entries[-1] if entries else None
        if current is None or (is_degree and "degree" in current) or (
            is_school and not is_degree and "institution" in current
        ):
            if not (text or start or end):
                continue
            current = {"details": []}
            entries.append(current)

        if start or end:
            current.setdefault("start", start)
            current.setdefault("end", end)
        if not text:
            continue
        if is_degree and "degree" not in current:
            degree, _, rest = text.partition(",")
            current["degree"] = degree
            if rest.strip() and "institution" not in current:
                current["institution"] = rest
        elif "institution" not in current and (is_school or "degree" not in current):
            current["institution"] = text
        else:
            current["details"].append(text)

    return [
        EducationItem(
            institution=_clip(e.get("institution", "")),
            degree=_clip(e.get("degree", "")),
            start=e.get("start", ""),
            end=e.get("end", ""),
            details=[_clip(d, 500) for d in e["details"]][:15],
        )
        for e in entries
        if e.get("institution") or e.get("degree")
    ][:10]


def _parse_skills(lines: list[str]) -> list[SkillGroup]:
    groups: list[SkillGroup] = []
    loose: list[str] = []
    for raw in lines:
        line = (_bullet(raw.strip()) or raw).strip()
        if not line:
            continue
        name = ""
        label, sep, rest = line.partition(":")
        if sep and 0 < len(label) <= 30:
            name, line = label.strip(), rest
        skills = [_clip(s) for s in SKILL_SPLIT_RE.split(line) if s.strip() and len(s.strip()) <= 60]
        if name:
            groups.append(SkillGroup(name=_clip(name), skills=skills[:60]))
        else:
            loose.extend(skills)
    if loose:
        groups.insert(0, SkillGroup(skills=list(dict.fromkeys(loose))[:60]))
    return groups[:10]


def _parse_projects(lines: list[str]) -> list[ProjectItem]:
    projects: list[dict] = []
    last_bullet: str | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        bullet = _bullet(line)
        if bullet is not None:
            if not projects:
                projects.append({"name": "", "url": "", "bullets": []})
            projects[-1]["bullets"].append(bullet)
            last_bullet = bullet
        elif _is_continuation(line, last_bullet) and projects and projects[-1]["bullets"]:
            projects[-1]["bullets"][-1] += " " + line
        else:
            last_bullet = None
            links = extract_links(line)
            name = line
            for link in links:
                name = name.replace(link, "")
            projects.append({"name": name.strip(" |–—-"), "url": links[0] if links else "", "bullets": []})
    return [
        ProjectItem(name=_clip(p["name"]), url=_clip(p["url"]), bullets=[_clip(b, 500) for b in p["bullets"]][:15])
        for p in projects
        if p["name"] or p["bullets"]
    ][:15]


def _parse_certifications(lines: list[str]) -> list[CertificationItem]:
    certs = []
    for raw in lines:
        line = (_bullet(raw.strip()) or raw).strip()
        if not line:
            continue
        date = ""
        dates = list(SINGLE_DATE_RE.finditer(line))
        if dates:
            match = dates[-1]
            date = _to_date(match.group("m"), None, match.group("y"))
            line = (line[: match.start()] + line[match.end():]).strip()
        parts = [p.strip(" ()") for p in SPLIT_RE.split(line) if p.strip(" ()")]
        name, issuer = (parts[0], parts[1]) if len(parts) > 1 else (line.strip(" |,–—-()"), "")
        certs.append(CertificationItem(name=_clip(name), issuer=_clip(issuer), date=date))
    return certs[:20]


def _parse_basics(header: list[str], summary_lines: list[str], full_text: str) -> Basics:
    lines = [line.strip() for line in header if line.strip()]
    header_text = "\n".join(lines)
    emails = extract_emails(header_text) or extract_emails(full_text)
    phones = extract_phones(header_text) or extract_phones(full_text)
    links = extract_links(header_text)

    def is_contactish(line: str) -> bool:
        return "@" in line or "http" in line or any(ch.isdigit() for ch in line) or "|" in line

    name = headline = location = ""
    summary_parts = list(summary_lines)
    for line in lines:
        if not name and not is_contactish(line) and len(line.split()) <= 5:
            name = line
        elif name and not headline and not is_contactish(line) and len(line.split()) <= 10:
            headline = line
        elif len(line.split()) > 12 and not summary_lines:
            summary_parts.append(line)
        for part in CONTACT_SPLIT_RE.split(line):
            part = part.strip()
            if (
                not location and "," in part and len(part) < 50
                and "@" not in part and "http" not in part and not any(ch.isdigit() for ch in part)
            ):
                location = part

    summary = " ".join(p.strip() for p in summary_parts if p.strip())
    return Basics(
        name=_clip(name),
        headline=_clip(headline),
        email=_clip(emails[0]) if emails else "",
        phone=_clip(phones[0]) if phones else "",
        location=_clip(location),
        links=[Link(url=_clip(link)) for link in links[:6]],
        summary=summary[:2000],
    )


def document_from_text(text: str) -> ResumeDocument:
    lines = text.splitlines()
    header, sections = _split_sections(lines)
    return ResumeDocument(
        basics=_parse_basics(header, sections.get("summary", []), text),
        experience=_parse_experience(sections.get("experience", [])),
        education=_parse_education(sections.get("education", [])),
        skills=_parse_skills(sections.get("skills", [])),
        projects=_parse_projects(sections.get("projects", [])),
        certifications=_parse_certifications(sections.get("certifications", [])),
    )
