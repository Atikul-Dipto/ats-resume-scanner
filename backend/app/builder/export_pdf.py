"""Text-based, single-column PDF export (fpdf2 — pure Python, no system deps).

Uses DejaVu Sans when available so non-Latin names and characters render;
otherwise falls back to the built-in Helvetica with characters outside
Latin-1 transliterated, so export never fails on an unusual character.
"""

from pathlib import Path

from fpdf import FPDF

from app.builder.layout import BULLET_GLYPH, Block, build_blocks
from app.core.config import get_settings
from app.schemas.resume import ResumeDocument

FONT_SEARCH_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/local/share/fonts",
]

TEMPLATES = {
    # name: (base font size, margin mm, line height factor, accent RGB)
    "classic": (10.5, 18, 1.45, (31, 41, 55)),
    "compact": (9.5, 13, 1.35, (17, 24, 39)),
}

_FALLBACK_REPLACEMENTS = {
    "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"',
    "”": '"', "•": "-", "…": "...", " ": " ",
}


def _find_font_dir() -> Path | None:
    configured = get_settings().pdf_font_dir
    for directory in ([configured] if configured else []) + FONT_SEARCH_DIRS:
        path = Path(directory)
        if (path / "DejaVuSans.ttf").exists() and (path / "DejaVuSans-Bold.ttf").exists():
            return path
    return None


class _ResumePDF(FPDF):
    def __init__(self, template: str):
        super().__init__(format="A4")
        size, margin, leading, accent = TEMPLATES.get(template, TEMPLATES["classic"])
        self.base_size = size
        self.leading = leading
        self.accent = accent
        self.set_margins(margin, margin, margin)
        self.set_auto_page_break(auto=True, margin=margin)

        font_dir = _find_font_dir()
        if font_dir:
            self.add_font("Body", "", str(font_dir / "DejaVuSans.ttf"))
            self.add_font("Body", "B", str(font_dir / "DejaVuSans-Bold.ttf"))
            oblique = font_dir / "DejaVuSans-Oblique.ttf"
            self.add_font("Body", "I", str(oblique if oblique.exists() else font_dir / "DejaVuSans.ttf"))
            self.body_font = "Body"
            self.is_unicode = True
        else:
            self.body_font = "Helvetica"
            self.is_unicode = False

    def clean(self, text: str) -> str:
        if self.is_unicode:
            return text
        for src, dst in _FALLBACK_REPLACEMENTS.items():
            text = text.replace(src, dst)
        return text.encode("latin-1", "replace").decode("latin-1")

    def line_height(self, size: float) -> float:
        return size * self.leading * 0.3528  # pt -> mm

    def write_block(self, block: Block) -> None:
        size = self.base_size
        text = self.clean(block.text)
        width = self.epw

        if block.kind == "name":
            self.set_font(self.body_font, "B", size + 9)
            self.set_text_color(*self.accent)
            self.multi_cell(width, self.line_height(size + 9), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "headline":
            self.set_font(self.body_font, "", size + 1.5)
            self.set_text_color(55, 65, 81)
            self.multi_cell(width, self.line_height(size + 1.5), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "contact":
            self.set_font(self.body_font, "", size - 0.5)
            self.set_text_color(75, 85, 99)
            self.multi_cell(width, self.line_height(size), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "heading":
            self.ln(self.line_height(size) * 0.6)
            self.set_font(self.body_font, "B", size + 1)
            self.set_text_color(*self.accent)
            self.multi_cell(width, self.line_height(size + 1), text.upper(), new_x="LMARGIN", new_y="NEXT")
            y = self.get_y()
            self.set_draw_color(209, 213, 219)
            self.set_line_width(0.3)
            self.line(self.l_margin, y, self.l_margin + width, y)
            self.ln(1.2)
        elif block.kind == "entry_title":
            self.ln(0.8)
            self.set_font(self.body_font, "B", size)
            self.set_text_color(17, 24, 39)
            self.multi_cell(width, self.line_height(size), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "entry_meta":
            self.set_font(self.body_font, "I", size - 0.5)
            self.set_text_color(75, 85, 99)
            self.multi_cell(width, self.line_height(size), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "bullet":
            self.set_font(self.body_font, "", size)
            self.set_text_color(31, 41, 55)
            glyph = self.clean(BULLET_GLYPH)
            indent = 4.5
            self.cell(indent, self.line_height(size), glyph)
            self.multi_cell(width - indent, self.line_height(size), text, new_x="LMARGIN", new_y="NEXT")
        else:  # line
            self.set_font(self.body_font, "", size)
            self.set_text_color(31, 41, 55)
            self.multi_cell(width, self.line_height(size), text, new_x="LMARGIN", new_y="NEXT")


def render_pdf(doc: ResumeDocument) -> bytes:
    pdf = _ResumePDF(doc.template)
    pdf.set_title(doc.basics.name or "Resume")
    pdf.set_creator("ATS Resume Builder")
    pdf.add_page()
    for block in build_blocks(doc):
        pdf.write_block(block)
    return bytes(pdf.output())
