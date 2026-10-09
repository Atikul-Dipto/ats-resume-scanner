"""Text-based, single-column PDF export (fpdf2: pure Python, no system deps).

Fonts are bundled in builder/fonts (Latin Modern for the LaTeX templates,
Source Sans 3 for the modern ones), and the browser preview loads the same
files, so line breaks and alignment in the preview match the download.
Unlike a real LaTeX build there are no ligatures or glyph-name tricks: every
character is written as itself, so "office" extracts as "office", never as
"oﬃce". Characters a bundled font lacks fall back to DejaVu Sans when it
is installed; if the bundled fonts are missing entirely, the built-in
Helvetica is used with characters outside Latin-1 transliterated, so export
never fails on an unusual character.

Geometry is mirrored in frontend/src/builder/resume-paper.css. If you change a
size or gap here, change it there too.
"""

from functools import cache
from pathlib import Path

from fontTools.ttLib import TTFont
from fpdf import FPDF

from app.builder.layout import Block, build_blocks
from app.builder.templates import Style, resolve_style
from app.core.config import get_settings
from app.schemas.resume import ResumeDocument

BUNDLED_FONT_DIR = Path(__file__).with_name("fonts")
FONT_FILES = {
    "lmroman": {"": "lmroman10-regular.otf", "B": "lmroman10-bold.otf",
                "I": "lmroman10-italic.otf", "BI": "lmroman10-bolditalic.otf"},
    "lmsans": {"": "lmsans10-regular.otf", "B": "lmsans10-bold.otf",
               "I": "lmsans10-oblique.otf", "BI": "lmsans10-boldoblique.otf"},
    "sourcesans": {"": "SourceSans3-Regular.ttf", "B": "SourceSans3-Bold.ttf",
                   "I": "SourceSans3-It.ttf", "BI": "SourceSans3-BoldIt.ttf"},
    "ebgaramond": {"": "EBGaramond-Regular.otf", "B": "EBGaramond-Bold.otf",
                   "I": "EBGaramond-Italic.otf", "BI": "EBGaramond-BoldItalic.otf"},
    "charter": {"": "XCharter-Roman.otf", "B": "XCharter-Bold.otf",
                "I": "XCharter-Italic.otf", "BI": "XCharter-BoldItalic.otf"},
    "lato": {"": "Lato-Regular.ttf", "B": "Lato-Bold.ttf", "I": "Lato-Italic.ttf", "BI": "Lato-BoldItalic.ttf"},
    "roboto": {"": "Roboto-Regular.otf", "B": "Roboto-Bold.otf",
               "I": "Roboto-Italic.otf", "BI": "Roboto-BoldItalic.otf"},
    # Roboto Slab has no italics; its upright faces stand in (the preview does the same).
    "robotoslab": {"": "RobotoSlab-Regular.otf", "B": "RobotoSlab-Bold.otf",
                   "I": "RobotoSlab-Regular.otf", "BI": "RobotoSlab-Bold.otf"},
}
FONT_SEARCH_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/local/share/fonts",
]

PT = 25.4 / 72  # mm per point
TEXT = (31, 41, 55)
STRONG = (17, 24, 39)
MUTED = (75, 85, 99)

# Shared with resume-paper.css.
NAME_LEADING = 1.2
HEADING_SCALE = 1.15
HEADING_LEADING = 1.25
SMALLCAPS_SCALE = 0.8
BULLET_INDENT = 4.5
BULLET_GLYPH_X = 1.0
ASIDE_GAP = 3.0
SHORT_BAR = 12.0  # mm, the "short" heading style's underline

_FALLBACK_REPLACEMENTS = {
    "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"',
    "”": '"', "•": "-", "›": ">", "…": "...", " ": " ",
}


def _find_font_dir() -> Path | None:
    """DejaVu, used only for glyphs the bundled fonts lack (e.g. Bengali digits)."""
    configured = get_settings().pdf_font_dir
    for directory in ([configured] if configured else []) + FONT_SEARCH_DIRS:
        path = Path(directory)
        if (path / "DejaVuSans.ttf").exists() and (path / "DejaVuSans-Bold.ttf").exists():
            return path
    return None


@cache
def _codepoints(path: str) -> frozenset[int]:
    return frozenset(TTFont(path, lazy=True)["cmap"].getBestCmap())


class _ResumePDF(FPDF):
    def __init__(self, style: Style):
        width, height = style.page_mm
        super().__init__(format=(width, height))
        self.style = style
        self.set_margins(style.margin, style.margin, style.margin)
        self.set_auto_page_break(auto=True, margin=style.margin)
        self.c_margin = 0  # text starts exactly at the page margin, as in the preview

        files = FONT_FILES[style.font]
        self.font_paths = {s: BUNDLED_FONT_DIR / f for s, f in files.items()}
        self.is_unicode = all(p.exists() for p in self.font_paths.values())
        self._registered: set[str] = set()

    def enable_fallback(self, text: str) -> None:
        if not self.is_unicode:
            return
        covered = _codepoints(str(self.font_paths[""]))
        if all(ord(ch) in covered or ch.isspace() for ch in text):
            return
        font_dir = _find_font_dir()
        if font_dir:
            self.add_font("fallback", "", str(font_dir / "DejaVuSans.ttf"))
            self.add_font("fallback", "B", str(font_dir / "DejaVuSans-Bold.ttf"))
            self.set_fallback_fonts(["fallback"], exact_match=False)

    def use(self, style: str, size: float) -> None:
        if not self.is_unicode:
            self.set_font("Helvetica", style, size)
            return
        if style not in self._registered:
            self.add_font("body", style, str(self.font_paths[style]))
            self._registered.add(style)
        self.set_font("body", style, size)

    def clean(self, text: str) -> str:
        if self.is_unicode:
            return text
        for src, dst in _FALLBACK_REPLACEMENTS.items():
            text = text.replace(src, dst)
        return text.encode("latin-1", "replace").decode("latin-1")

    # --- geometry -------------------------------------------------------
    def lh(self, size: float) -> float:
        return size * self.style.line_height * PT

    def keep(self, height: float) -> None:
        """Start a new page unless `height` fits on this one."""
        if self.get_y() + height > self.page_break_trigger:
            self.add_page()

    def at_page_top(self) -> bool:
        return self.get_y() <= self.t_margin + 0.01

    # --- blocks ---------------------------------------------------------
    def write_block(self, block: Block, previous: Block | None) -> None:
        st = self.style
        size = st.font_size
        align = "C" if st.header_align == "center" else "L"
        text = self.clean(block.text)

        if block.kind == "name":
            self.use("B", st.name_size)
            self.set_text_color(*st.accent_rgb)
            self.multi_cell(self.epw, st.name_size * NAME_LEADING * PT, text, align=align,
                            new_x="LMARGIN", new_y="NEXT")
            self.ln(0.6)
        elif block.kind == "headline":
            self.use("", size + 1.5)
            self.set_text_color(*(st.accent_rgb if st.headline_color == "accent" else TEXT))
            self.multi_cell(self.epw, self.lh(size + 1.5), text, align=align, new_x="LMARGIN", new_y="NEXT")
            self.ln(0.4)
        elif block.kind == "contact":
            self.use("", size - 0.5)
            self.set_text_color(*MUTED)
            self.multi_cell(self.epw, self.lh(size), text, align=align, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "heading":
            self.heading(text)
        elif block.kind == "entry_title":
            if previous is not None and previous.kind != "heading":
                self.ln(1.2)
            self.row(text, self.clean(block.aside), "B", STRONG)
        elif block.kind == "entry_meta":
            self.use("I", size - 0.5)
            self.set_text_color(*MUTED)
            self.multi_cell(self.epw, self.lh(size), text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "bullet":
            self.use("", size)
            self.set_text_color(*TEXT)
            h = self.lh(size)
            self.keep(h)
            self.set_x(self.l_margin + BULLET_GLYPH_X)
            # The trailing space is a real character, so extractors always
            # separate the glyph from the text however narrow the font's bullet.
            self.cell(BULLET_INDENT - BULLET_GLYPH_X, h, self.clean(st.bullet) + " ")
            self.multi_cell(self.epw - BULLET_INDENT, h, text, new_x="LMARGIN", new_y="NEXT")
        elif block.kind == "skill":
            h = self.lh(size)
            self.set_text_color(*TEXT)
            self.set_x(self.l_margin)
            self.use("B", size)
            self.write(h, self.clean(f"{block.label}:"))
            self.use("", size)
            self.write(h, self.clean(block.text[len(block.label) + 1:]))
            self.ln(h)
        else:  # line
            self.use("", size)
            self.set_text_color(*TEXT)
            self.multi_cell(self.epw, self.lh(size), text, new_x="LMARGIN", new_y="NEXT")

    def row(self, text: str, aside: str, left_style: str, color) -> None:
        """Left text, plus an optional right-aligned aside on its first line."""
        size = self.style.font_size
        h = self.lh(size)
        self.keep(h)
        y = self.get_y()
        aside_w = 0.0
        if aside:
            self.use("I", size)
            self.set_text_color(*MUTED)
            aside_w = self.get_string_width(aside)
            self.set_xy(self.l_margin + self.epw - aside_w, y)
            self.cell(aside_w, h, aside)
        self.set_xy(self.l_margin, y)
        if text:
            self.use(left_style, size)
            self.set_text_color(*color)
            width = self.epw - (aside_w + ASIDE_GAP if aside else 0)
            self.multi_cell(width, h, text, new_x="LMARGIN", new_y="NEXT")
        else:
            self.set_y(y + h)

    def heading_runs(self, text: str, size: float) -> list[tuple[str, float]]:
        if self.style.heading_case != "smallcaps":
            return [(text, size)]
        runs: list[tuple[str, float]] = []
        for i, word in enumerate(text.split(" ")):
            if i:
                runs.append((" ", size * SMALLCAPS_SCALE))
            runs.append((word[:1], size))
            if word[1:]:
                runs.append((word[1:], size * SMALLCAPS_SCALE))
        return runs

    def heading(self, text: str) -> None:
        st = self.style
        size = st.font_size * HEADING_SCALE
        h = size * HEADING_LEADING * PT
        if not self.at_page_top():
            self.ln(self.lh(st.font_size) * 0.75)
        # Never leave a heading stranded at the bottom of a page.
        self.keep(h + 2.5 + 2 * self.lh(st.font_size))

        runs = self.heading_runs(text, size)
        widths = []
        for run, run_size in runs:
            self.use("B", run_size)
            widths.append(self.get_string_width(run))
        total = sum(widths)
        left, right = self.l_margin, self.l_margin + self.epw
        x = left + (self.epw - total) / 2 if st.heading_align == "center" else left

        y = self.get_y()
        baseline = y + h / 2 + 0.3 * size * PT
        self.set_text_color(*st.accent_rgb)
        cursor = x
        for (run, run_size), width in zip(runs, widths, strict=False):
            self.use("B", run_size)
            self.text(cursor, baseline, run)
            cursor += width

        self.set_draw_color(*st.rule_rgb)
        if st.heading_style == "rule":
            self.set_line_width(0.3)
            self.line(left, y + h + 0.3, right, y + h + 0.3)
            self.set_y(y + h + 1.8)
        elif st.heading_style == "double":
            self.set_line_width(0.29)
            self.line(left, y + h + 0.3, right, y + h + 0.3)
            self.line(left, y + h + 0.9, right, y + h + 0.9)
            self.set_y(y + h + 2.4)
        elif st.heading_style == "short":
            # A short, thick accent bar under the heading text (a stroked line,
            # not a filled rectangle, so no parser mistakes it for a table cell).
            self.set_draw_color(*st.accent_rgb)
            self.set_line_width(0.8)
            start = x + (total - SHORT_BAR) / 2 if st.heading_align == "center" else x
            self.line(start, y + h + 0.6, start + SHORT_BAR, y + h + 0.6)
            self.set_y(y + h + 2.2)
        elif st.heading_style == "line":
            self.set_line_width(0.4)
            mid = baseline - 0.3 * size * PT
            if cursor + 2.5 < right:
                self.line(cursor + 2.5, mid, right, mid)
            if st.heading_align == "center" and x - 2.5 > left:
                self.line(left, mid, x - 2.5, mid)
            self.set_y(y + h + 1.2)
        else:
            self.set_y(y + h + 1.2)


def render_pdf(doc: ResumeDocument) -> bytes:
    style = resolve_style(doc)
    blocks = build_blocks(doc, style)
    pdf = _ResumePDF(style)
    pdf.set_title(doc.basics.name or "Resume")
    pdf.set_author(doc.basics.name or "")
    pdf.set_creator("Prottoy Resume Builder")
    pdf.set_lang("en")
    pdf.enable_fallback("".join(b.text + b.aside for b in blocks))
    pdf.add_page()
    previous = None
    for block in blocks:
        pdf.write_block(block, previous)
        previous = block
    return bytes(pdf.output())
