"""ResumeDocument -> a flat list of layout blocks.

This is the single source of truth for what a built resume *says* and in what
order. The plain-text renderer (used for live scoring) and the PDF and DOCX
exporters all consume these same blocks, so the score shown while editing is
the score of the exact text an ATS will extract from the downloaded file.

The layout is deliberately ATS-conservative: one column, standard section
headings, contact details in the body (never a header/footer), real text (no
images or tables), dates as plain text right under each role.
"""

from dataclasses import dataclass
from typing import Literal

from app.schemas.resume import ResumeDocument

BlockKind = Literal["name", "headline", "contact", "heading", "entry_title", "entry_meta", "bullet", "line"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEPARATOR = " | "
DASH = " – "


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str


def format_date(value: str) -> str:
    if not value:
        return ""
    year, _, month = value.partition("-")
    return f"{MONTHS[int(month) - 1]} {year}" if month else year


def format_range(start: str, end: str, current: bool = False) -> str:
    start_text = format_date(start)
    end_text = "Present" if current else format_date(end)
    if start_text and end_text:
        return f"{start_text}{DASH}{end_text}"
    return start_text or end_text


def _join(*parts: str, sep: str = SEPARATOR) -> str:
    return sep.join(p for p in parts if p)


def build_blocks(doc: ResumeDocument) -> list[Block]:
    blocks: list[Block] = []
    basics = doc.basics

    if basics.name:
        blocks.append(Block("name", basics.name))
    if basics.headline:
        blocks.append(Block("headline", basics.headline))
    contact = _join(basics.email, basics.phone, basics.location, *(link.url for link in basics.links))
    if contact:
        blocks.append(Block("contact", contact))

    if basics.summary:
        blocks.append(Block("heading", "Summary"))
        blocks.extend(Block("line", para) for para in basics.summary.splitlines() if para.strip())

    experience = [e for e in doc.experience if e.title or e.company or e.bullets]
    if experience:
        blocks.append(Block("heading", "Experience"))
        for item in experience:
            blocks.append(Block("entry_title", _join(item.title, item.company, sep=", ")))
            meta = _join(format_range(item.start, item.end, item.current), item.location)
            if meta:
                blocks.append(Block("entry_meta", meta))
            blocks.extend(Block("bullet", b) for b in item.bullets if b)

    education = [e for e in doc.education if e.institution or e.degree]
    if education:
        blocks.append(Block("heading", "Education"))
        for item in education:
            blocks.append(Block("entry_title", _join(item.degree, item.institution, sep=", ")))
            meta = _join(format_range(item.start, item.end), item.location)
            if meta:
                blocks.append(Block("entry_meta", meta))
            # Plain lines, not bullets: "GPA 3.8" isn't an achievement and
            # shouldn't be judged for action verbs and metrics.
            blocks.extend(Block("line", d) for d in item.details if d)

    skill_groups = [g for g in doc.skills if any(g.skills)]
    if skill_groups:
        blocks.append(Block("heading", "Skills"))
        for group in skill_groups:
            listed = ", ".join(s for s in group.skills if s)
            blocks.append(Block("line", f"{group.name}: {listed}" if group.name else listed))

    projects = [p for p in doc.projects if p.name or p.bullets]
    if projects:
        blocks.append(Block("heading", "Projects"))
        for project in projects:
            blocks.append(Block("entry_title", _join(project.name, project.url)))
            blocks.extend(Block("bullet", b) for b in project.bullets if b)

    certifications = [c for c in doc.certifications if c.name]
    if certifications:
        blocks.append(Block("heading", "Certifications"))
        for cert in certifications:
            blocks.append(Block("line", _join(cert.name, cert.issuer, format_date(cert.date))))

    return blocks


BULLET_GLYPH = "•"


def render_text(doc: ResumeDocument) -> str:
    """Plain text in the same order and wording as the exported files."""
    lines: list[str] = []
    for block in build_blocks(doc):
        if block.kind == "heading":
            if lines:
                lines.append("")
            lines.append(block.text.upper())
        elif block.kind == "bullet":
            lines.append(f"{BULLET_GLYPH} {block.text}")
        else:
            lines.append(block.text)
    return "\n".join(lines)
