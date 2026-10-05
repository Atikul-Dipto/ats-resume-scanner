"""Engineering disciplines the job board covers, and rule-based classification.

Rules, not a model: titles are short and the vocabulary is distinctive enough
that ordered keyword rules are accurate, explainable, and trivially testable.
Order matters — "data engineer" is Data, not Software; "electrical
maintenance engineer" is Electrical, not Mechanical.
"""

import re

DISCIPLINES: dict[str, str] = {
    "data": "Data & Analytics",
    "software": "Software & IT",
    "civil": "Civil & Construction",
    "electrical": "Electrical & Electronics",
    "mechanical": "Mechanical, Industrial & Textile",
}

_TITLE_RULES: list[tuple[str, re.Pattern]] = [
    ("data", re.compile(
        r"\b(data|analytics?|business analyst|bi (developer|analyst|engineer)|business intelligence|"
        r"mis (executive|officer|analyst)|reporting analyst|insights?|statistician|machine learning|ml engineer)\b")),
    ("civil", re.compile(
        r"\b(civil|structural|construction|site engineer|quantity surveyor|qs engineer|estimation engineer|"
        r"geotechnical|surveyor|plumbing engineer)\b")),
    ("electrical", re.compile(
        r"\b(electrical|electronics?|eee|power (plant|system)|substation|plc|scada|instrumentation|"
        r"embedded|telecom|rf engineer|solar)\b")),
    ("mechanical", re.compile(
        r"\b(mechanical|industrial engineer|production (engineer|manager|officer)|textile|garments?|"
        r"knitting|dyeing|washing|merchandiser|apparel|hvac|maintenance engineer|manufacturing|"
        r"ie (executive|officer|engineer)|quality (control|assurance) (engineer|officer|executive))\b")),
    ("software", re.compile(
        r"\b(software|developer|programmer|front[- ]?end|back[- ]?end|full[- ]?stack|devops|sre|"
        r"site reliability|sqa|qa engineer|test automation|web|mobile|android|ios|flutter|cloud|"
        r"network (engineer|administrator)|system administrator|sysadmin|it (support|officer|executive)|"
        r"security engineer|cyber ?security|platform engineer|tech lead|engineering manager)\b")),
]

# Signature skills per discipline, used to classify a *candidate* when their
# title alone is ambiguous (e.g. "Engineer" or no title at all).
_SIGNATURE_SKILLS: dict[str, set[str]] = {
    "data": {"power bi", "tableau", "dax", "power query", "looker", "statistics", "data analysis",
             "data visualization", "business intelligence", "excel", "sql", "pandas", "a/b testing"},
    "software": {"javascript", "typescript", "react", "node.js", "django", "laravel", "spring boot",
                 "docker", "kubernetes", "java", "c#", ".net", "flutter", "android", "ios", "git"},
    "civil": {"autocad", "staad pro", "etabs", "revit", "estimation", "boq", "quantity surveying",
              "structural design", "site supervision", "surveying", "primavera p6", "rcc design"},
    "electrical": {"etap", "plc", "scada", "substation", "power systems", "switchgear", "transformer",
                   "autocad electrical", "pcb design", "embedded systems", "microcontroller", "solar pv"},
    "mechanical": {"solidworks", "catia", "ansys", "hvac", "lean manufacturing", "six sigma",
                   "production planning", "industrial engineering", "garments", "knitting", "dyeing",
                   "merchandising", "line balancing", "smv", "boiler", "preventive maintenance"},
}


def classify_title(title: str) -> str | None:
    """Discipline for a job title, or None if it isn't an engineering/data role."""
    lowered = (title or "").lower()
    for discipline, pattern in _TITLE_RULES:
        if pattern.search(lowered):
            return discipline
    return None


def classify_profile(title: str | None, skills: list[str]) -> str | None:
    """Best-guess discipline for a candidate: title first, signature skills as tie-break/fallback."""
    lowered_skills = {s.lower() for s in skills}
    votes = {d: len(lowered_skills & sig) for d, sig in _SIGNATURE_SKILLS.items()}
    by_title = classify_title(title or "")
    if by_title:
        # A clear skills majority elsewhere beats a vague title ("Engineer at X").
        best = max(votes, key=votes.get)
        if votes[best] >= 3 and votes[best] >= 2 * max(votes[by_title], 1):
            return best
        return by_title
    best = max(votes, key=votes.get)
    return best if votes[best] >= 2 else None
