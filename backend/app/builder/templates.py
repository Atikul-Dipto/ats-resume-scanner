"""Template presets plus a resume's own design overrides -> one resolved Style.

templates.json is shared with the frontend (frontend/src/builder/templates.js
imports it), so the in-browser preview and the exported files read the same
numbers. Every option here is a typographic choice inside one ATS-safe
layout: single column, real text, standard headings. None of them can add a
table, a second column, an image or a header/footer.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.schemas.resume import ResumeDocument

_DATA = json.loads(Path(__file__).with_name("templates.json").read_text(encoding="utf-8"))

TEMPLATES: dict[str, dict] = _DATA["templates"]
FONTS: dict[str, dict] = _DATA["fonts"]
SECTION_KEYS: tuple[str, ...] = tuple(_DATA["sections"])
SECTION_TITLES: dict[str, str] = _DATA["section_titles"]
PAPER_MM: dict[str, tuple[float, float]] = {k: tuple(v) for k, v in _DATA["paper"].items()}
DEFAULT_TEMPLATE = "classic"


@dataclass(frozen=True)
class Style:
    font: str
    font_size: float
    name_size: float
    margin: float
    line_height: float
    accent: str
    header_align: str
    name_case: str
    heading_style: str
    heading_case: str
    heading_align: str
    date_position: str
    paper: str
    section_order: tuple[str, ...]

    @property
    def accent_rgb(self) -> tuple[int, int, int]:
        return hex_to_rgb(self.accent)

    @property
    def rule_rgb(self) -> tuple[int, int, int]:
        """Rules are the accent, lightened, so a black accent still gets a soft line."""
        return mix_with_white(self.accent_rgb, 0.45 if self.heading_style == "rule" else 0.2)

    @property
    def page_mm(self) -> tuple[float, float]:
        return PAPER_MM[self.paper]


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix_with_white(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(c + (255 - c) * amount) for c in rgb)  # type: ignore[return-value]


def normalize_order(order) -> tuple[str, ...]:
    """Known keys in the given order, duplicates dropped, missing ones appended."""
    seen = [key for key in dict.fromkeys(order or ()) if key in SECTION_KEYS]
    return tuple(seen + [key for key in SECTION_KEYS if key not in seen])


def resolve_style(doc: ResumeDocument) -> Style:
    base = TEMPLATES.get(doc.template, TEMPLATES[DEFAULT_TEMPLATE])["style"]
    overrides = {k: v for k, v in doc.style.model_dump().items() if v is not None}
    merged = {**base, **overrides}
    merged["section_order"] = normalize_order(merged.get("section_order"))
    return Style(**merged)
