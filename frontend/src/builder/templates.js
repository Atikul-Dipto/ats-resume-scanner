// Template presets, shared verbatim with the backend exporters
// (backend/app/builder/templates.json) so the preview uses the same numbers
// as the PDF, DOCX and LaTeX files. Mirrors backend/app/builder/templates.py.
import DATA from "../../../backend/app/builder/templates.json";

export const TEMPLATES = DATA.templates;
export const TEMPLATE_IDS = Object.keys(DATA.templates);
export const FONTS = DATA.fonts;
export const SECTION_KEYS = DATA.sections;
export const SECTION_TITLES = DATA.section_titles;
export const PAPER_MM = DATA.paper;

// CSS families for the bundled fonts (see resume-paper.css @font-face).
export const FONT_CSS = {
  lmroman: '"Resume LM Roman", "Latin Modern Roman", "Computer Modern", Georgia, serif',
  lmsans: '"Resume LM Sans", "Latin Modern Sans", "Segoe UI", sans-serif',
  sourcesans: '"Resume Source Sans", "Source Sans 3", "Segoe UI", sans-serif',
  ebgaramond: '"Resume EB Garamond", "EB Garamond", Garamond, serif',
  charter: '"Resume Charter", "XCharter", Charter, Georgia, serif',
  lato: '"Resume Lato", Lato, "Segoe UI", sans-serif',
  roboto: '"Resume Roboto", Roboto, Arial, sans-serif',
  robotoslab: '"Resume Roboto Slab", "Roboto Slab", Rockwell, serif',
};

export const CATEGORIES = DATA.categories;

export function normalizeOrder(order) {
  const seen = [...new Set(order || [])].filter((k) => SECTION_KEYS.includes(k));
  return [...seen, ...SECTION_KEYS.filter((k) => !seen.includes(k))];
}

export function resolveStyle(doc) {
  const base = (TEMPLATES[doc.template] || TEMPLATES.classic).style;
  const overrides = Object.fromEntries(
    Object.entries(doc.style || {}).filter(([, v]) => v !== null && v !== undefined)
  );
  const merged = { ...base, ...overrides };
  return { ...merged, section_order: normalizeOrder(merged.section_order) };
}

// Switching templates drops design overrides (so the new look applies in
// full) but keeps a custom section order, which is about content, not looks.
export function withTemplate(doc, id) {
  const kept = doc.style?.section_order ? { section_order: doc.style.section_order } : {};
  return { ...doc, template: id, style: kept };
}

function hexToRgb(hex) {
  const v = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16));
}

const mixWithWhite = (rgb, amount) => rgb.map((c) => Math.round(c + (255 - c) * amount));

// Same lightening as Style.rule_rgb in templates.py.
export function ruleColor(style) {
  const [r, g, b] = mixWithWhite(hexToRgb(style.accent), style.heading_style === "rule" ? 0.45 : 0.2);
  return `rgb(${r}, ${g}, ${b})`;
}

export const ACCENT_SWATCHES = [
  "#000000", "#1F2937", "#3873B3", "#0A66C2", "#0F766E", "#15803D", "#7C3AED", "#BE185D", "#DC3522", "#B45309",
];
