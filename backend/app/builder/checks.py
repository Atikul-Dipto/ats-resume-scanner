"""Structural checks for a resume being built.

The builder's layout can't have the file-level problems the upload scanner
looks for (images, tables, columns, header/footer contact info), so these
checks take that slot in the score: missing contact details, roles without
dates or bullets, overlong bullets. Same issue shape and severity scale as
analysis/formatting_checker.py, so the scorer treats them identically.
"""

from app.schemas.resume import ResumeDocument

MAX_BULLET_CHARS = 260
IDEAL_BULLETS = (2, 6)
MAX_WORDS_TWO_PAGES = 1000


def _issue(severity: str, message: str, location: str | None = None) -> dict:
    return {"severity": severity, "message": message, "location": location}


def _role_label(title: str, company: str, index: int) -> str:
    return " at ".join(p for p in (title, company) if p) or f"Role {index + 1}"


def check_document(doc: ResumeDocument) -> list[dict]:
    issues: list[dict] = []
    basics = doc.basics

    if not basics.name:
        issues.append(_issue("critical", "Add your full name at the top of the resume.", "Contact"))
    if not basics.email and not basics.phone:
        issues.append(_issue("critical", "Add an email address or phone number so recruiters can reach you.", "Contact"))
    elif not basics.email:
        issues.append(_issue("warning", "Add an email address — most ATS profiles require one.", "Contact"))

    roles = [e for e in doc.experience if e.title or e.company or e.bullets]
    if not roles and not doc.education:
        issues.append(_issue("critical", "Add at least one work experience or education entry.", "Experience"))

    for i, role in enumerate(roles):
        label = _role_label(role.title, role.company, i)
        if not role.title or not role.company:
            issues.append(_issue("warning", f"Give '{label}' both a job title and a company name.", label))
        if not role.start:
            issues.append(_issue("warning", f"Add a start date to '{label}' — ATS parsers use dates to compute experience.", label))
        elif not role.current and role.end and role.end < role.start:
            issues.append(_issue("warning", f"'{label}' ends before it starts — check the dates.", label))
        elif not role.current and not role.end:
            issues.append(_issue("info", f"Add an end date to '{label}', or mark it as your current role.", label))

        bullets = [b for b in role.bullets if b]
        if len(bullets) < IDEAL_BULLETS[0]:
            issues.append(_issue("warning", f"Add {IDEAL_BULLETS[0]}–{IDEAL_BULLETS[1]} achievement bullets to '{label}'.", label))
        elif len(bullets) > IDEAL_BULLETS[1]:
            issues.append(_issue("info", f"'{label}' has {len(bullets)} bullets; trim to your strongest {IDEAL_BULLETS[1]}.", label))
        long_bullets = sum(1 for b in bullets if len(b) > MAX_BULLET_CHARS)
        if long_bullets:
            issues.append(_issue("info", f"{long_bullets} bullet(s) in '{label}' run past ~2 lines; tighten them.", label))

    if not doc.all_skills():
        issues.append(_issue("warning", "Add a skills list — it's the first thing keyword filters read.", "Skills"))

    word_count = sum(len(chunk.split()) for chunk in _all_text(doc))
    if word_count > MAX_WORDS_TWO_PAGES:
        issues.append(_issue(
            "info",
            f"About {word_count} words — likely more than 2 pages. Trim older or less relevant detail.",
            "Whole document",
        ))

    return issues


def _all_text(doc: ResumeDocument):
    yield doc.basics.summary
    for role in doc.experience:
        yield from role.bullets
    for project in doc.projects:
        yield from project.bullets
    for edu in doc.education:
        yield from edu.details
