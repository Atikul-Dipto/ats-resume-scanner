"""ResumeDocument -> a flat list of layout blocks.

This is the single source of truth for what a built resume *says* and in what
order. The plain-text renderer (used for live scoring) and the PDF, DOCX and
LaTeX exporters all consume these same blocks, so the score shown while
editing is the score of the exact text an ATS will extract from the
downloaded file. Anything that changes the extracted text (letter case,
section order, dates beside or below a role) is decided here, never in a
renderer.

The layout is deliberately ATS-conservative whatever the template: one
column, standard section headings, contact details in the body (never a
header/footer), real text (no images or tables). A right-aligned date sits on
the same text line as its role, so it extracts as "Title, Company Jan 2020 –
Present", which parsers read as one entry.
"""

from dataclasses import dataclass
from typing import Literal

from app.builder.templates import SECTION_TITLES, Style, resolve_style
from app.schemas.resume import ResumeDocument

BlockKind = Literal["name", "headline", "contact", "heading", "entry_title", "entry_meta", "bullet", "line", "skill"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEPARATOR = " | "
DASH = " – "


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str
    aside: str = ""  # right-aligned on the same line: dates, or a location
    label: str = ""  # bold lead-in of a skill line ("Languages" in "Languages: Python, SQL")
    parts: tuple[str, ...] = ()  # the contact line's items, so exporters can link them


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


def heading_text(key: str, style: Style) -> str:
    title = SECTION_TITLES[key]
    return title if style.heading_case == "normal" else title.upper()


def _entry(blocks: list[Block], title: str, dates: str, location: str, style: Style) -> None:
    if style.date_position == "right":
        blocks.append(Block("entry_title", title, aside=dates))
        if location:
            blocks.append(Block("entry_meta", location))
    else:
        blocks.append(Block("entry_title", title))
        meta = _join(dates, location)
        if meta:
            blocks.append(Block("entry_meta", meta))


def _summary(doc: ResumeDocument, style: Style) -> list[Block]:
    paras = [p for p in doc.basics.summary.splitlines() if p.strip()]
    return [Block("line", p) for p in paras]


def _experience(doc: ResumeDocument, style: Style) -> list[Block]:
    blocks: list[Block] = []
    for item in doc.experience:
        if not (item.title or item.company or any(item.bullets)):
            continue
        dates = format_range(item.start, item.end, item.current)
        _entry(blocks, _join(item.title, item.company, sep=", "), dates, item.location, style)
        blocks.extend(Block("bullet", b) for b in item.bullets if b)
    return blocks


def _education(doc: ResumeDocument, style: Style) -> list[Block]:
    blocks: list[Block] = []
    for item in doc.education:
        if not (item.institution or item.degree):
            continue
        dates = format_range(item.start, item.end)
        _entry(blocks, _join(item.degree, item.institution, sep=", "), dates, item.location, style)
        # Plain lines, not bullets: "GPA 3.8" isn't an achievement and
        # shouldn't be judged for action verbs and metrics.
        blocks.extend(Block("line", d) for d in item.details if d)
    return blocks


def _skills(doc: ResumeDocument, style: Style) -> list[Block]:
    blocks: list[Block] = []
    for group in doc.skills:
        listed = ", ".join(s for s in group.skills if s)
        if not listed:
            continue
        if group.name:
            blocks.append(Block("skill", f"{group.name}: {listed}", label=group.name))
        else:
            blocks.append(Block("line", listed))
    return blocks


def _projects(doc: ResumeDocument, style: Style) -> list[Block]:
    blocks: list[Block] = []
    for project in doc.projects:
        if not (project.name or any(project.bullets)):
            continue
        blocks.append(Block("entry_title", _join(project.name, project.url)))
        blocks.extend(Block("bullet", b) for b in project.bullets if b)
    return blocks


def _certifications(doc: ResumeDocument, style: Style) -> list[Block]:
    return [
        Block("line", _join(cert.name, cert.issuer, format_date(cert.date)))
        for cert in doc.certifications
        if cert.name
    ]


SECTION_BUILDERS = {
    "summary": _summary,
    "experience": _experience,
    "education": _education,
    "skills": _skills,
    "projects": _projects,
    "certifications": _certifications,
}


def build_blocks(doc: ResumeDocument, style: Style | None = None) -> list[Block]:
    style = style or resolve_style(doc)
    blocks: list[Block] = []
    basics = doc.basics

    if basics.name:
        blocks.append(Block("name", basics.name.upper() if style.name_case == "upper" else basics.name))
    if basics.headline:
        blocks.append(Block("headline", basics.headline))
    parts = tuple(p for p in (basics.email, basics.phone, basics.location, *(link.url for link in basics.links)) if p)
    if parts:
        blocks.append(Block("contact", SEPARATOR.join(parts), parts=parts))

    for key in style.section_order:
        body = SECTION_BUILDERS[key](doc, style)
        if body:
            blocks.append(Block("heading", heading_text(key, style)))
            blocks.extend(body)
    return blocks


BULLET_GLYPH = "•"


def block_line(block: Block) -> str:
    """One block as the single line of text an ATS extracts from the files."""
    if block.kind == "bullet":
        return f"{BULLET_GLYPH} {block.text}"
    return _join(block.text, block.aside, sep=" ")


def render_text(doc: ResumeDocument) -> str:
    """Plain text in the same order and wording as the exported files."""
    lines: list[str] = []
    for block in build_blocks(doc):
        if block.kind == "heading" and lines:
            lines.append("")
        lines.append(block_line(block))
    return "\n".join(lines)
