"""Single-column DOCX export with Word's own list bullets and no tables,
text boxes, headers or footers — the structures ATS parsers handle worst."""

import io

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Mm, Pt, RGBColor

from app.builder.layout import build_blocks
from app.schemas.resume import ResumeDocument

TEMPLATES = {
    # name: (base font size pt, margin mm, font)
    "classic": (10.5, 18, "Calibri"),
    "compact": (9.5, 13, "Calibri"),
}

ACCENT = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x4B, 0x55, 0x63)


def render_docx(doc: ResumeDocument) -> bytes:
    size, margin, font_name = TEMPLATES.get(doc.template, TEMPLATES["classic"])
    document = Document()

    for section in document.sections:
        section.top_margin = section.bottom_margin = Mm(margin)
        section.left_margin = section.right_margin = Mm(margin)

    normal = document.styles["Normal"]
    normal.font.name = font_name
    normal.font.size = Pt(size)
    normal.paragraph_format.space_after = Pt(1)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

    def paragraph(text: str, *, style: str | None = None, bold=False, italic=False,
                  pt: float = size, color: RGBColor | None = None, space_before: float = 0):
        para = document.add_paragraph(style=style)
        para.paragraph_format.space_before = Pt(space_before)
        run = para.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(pt)
        if color is not None:
            run.font.color.rgb = color
        return para

    for block in build_blocks(doc):
        if block.kind == "name":
            paragraph(block.text, bold=True, pt=size + 9, color=ACCENT)
        elif block.kind == "headline":
            paragraph(block.text, pt=size + 1.5, color=MUTED)
        elif block.kind == "contact":
            paragraph(block.text, pt=size - 0.5, color=MUTED)
        elif block.kind == "heading":
            paragraph(block.text.upper(), bold=True, pt=size + 1, color=ACCENT, space_before=8)
        elif block.kind == "entry_title":
            paragraph(block.text, bold=True, space_before=3)
        elif block.kind == "entry_meta":
            paragraph(block.text, italic=True, pt=size - 0.5, color=MUTED)
        elif block.kind == "bullet":
            paragraph(block.text, style="List Bullet")
        else:
            paragraph(block.text)

    document.core_properties.title = doc.basics.name or "Resume"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
