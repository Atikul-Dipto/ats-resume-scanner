import re

SECTION_PATTERNS = {
    "Contact Information": re.compile(r"@|\+?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}"),
    "Summary/Objective": re.compile(r"\b(summary|objective|profile)\b", re.IGNORECASE),
    "Work Experience": re.compile(
        r"\b(experience|employment history|work history)\b", re.IGNORECASE
    ),
    "Education": re.compile(r"\b(education|academic background)\b", re.IGNORECASE),
    "Skills": re.compile(r"\b(skills|technical skills|core competencies)\b", re.IGNORECASE),
}


def detect_sections(text: str) -> list[dict]:
    return [
        {"name": name, "found": bool(pattern.search(text))}
        for name, pattern in SECTION_PATTERNS.items()
    ]
