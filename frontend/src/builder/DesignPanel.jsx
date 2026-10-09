import { useId, useState } from "react";
import { isBlank, moveItem } from "./model.js";
import { ResumeThumbnail } from "./ResumePreview.jsx";
import {
  ACCENT_SWATCHES,
  CATEGORIES,
  FONT_CSS,
  FONTS,
  SECTION_TITLES,
  TEMPLATE_IDS,
  TEMPLATES,
  resolveStyle,
  withTemplate,
} from "./templates.js";

// Template gallery + design controls. Every option is typography inside one
// ATS-safe layout (single column, real text, standard headings), so nothing
// here can lower the ATS score; the export tests enforce that per template.

const SAMPLE = {
  template: "classic",
  style: {},
  basics: {
    name: "Jane Doe",
    headline: "Data Analyst",
    email: "jane@example.com",
    phone: "+1 415-555-0182",
    location: "Dhaka, Bangladesh",
    links: [{ url: "linkedin.com/in/janedoe" }],
    summary: "Data analyst with 4 years of experience turning operational data into dashboards and decisions.",
  },
  experience: [
    {
      title: "Data Analyst", company: "Acme Corp", location: "Dhaka", start: "2020-01", end: "", current: true,
      bullets: [
        "Built ETL pipelines with Python and Airflow, reducing report latency by 40%.",
        "Led migration of 30 dashboards to Power BI, saving 10 hours per week.",
      ],
    },
    {
      title: "Junior Analyst", company: "Beta Ltd", location: "", start: "2018-06", end: "2019-12", current: false,
      bullets: ["Automated weekly sales reporting in SQL, cutting turnaround from 2 days to 2 hours."],
    },
  ],
  education: [{ institution: "State University", degree: "BSc Computer Science", location: "", start: "2014", end: "2018", details: [] }],
  skills: [{ name: "Languages", skills: ["Python", "SQL"] }, { name: "Tools", skills: ["Power BI", "Tableau", "Airflow"] }],
  projects: [],
  certifications: [],
};

function Segmented({ label, value, options, onChange, wrap = false }) {
  const id = useId();
  return (
    <div className="design-field">
      <span className="field-label" id={id}>{label}</span>
      <div className={`seg-group seg-group--fill${wrap ? " seg-group--wrap" : ""}`} role="radiogroup" aria-labelledby={id}>
        {options.map(([optValue, optLabel, optStyle]) => (
          <button
            key={optValue}
            type="button"
            role="radio"
            aria-checked={value === optValue}
            className={`seg${value === optValue ? " is-active" : ""}`}
            style={optStyle}
            onClick={() => onChange(optValue)}
          >
            {optLabel}
          </button>
        ))}
      </div>
    </div>
  );
}

function Slider({ label, value, min, max, step, unit, onChange }) {
  const id = useId();
  return (
    <div className="design-field">
      <label className="field-label design-slider__label" htmlFor={id}>
        {label} <output htmlFor={id}>{value}{unit}</output>
      </label>
      <input id={id} className="design-slider" type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

export default function DesignPanel({ document: doc, onChange }) {
  const [category, setCategory] = useState("All");
  const style = resolveStyle(doc);
  const visible = TEMPLATE_IDS.filter((id) => category === "All" || TEMPLATES[id].category === category);
  const preset = TEMPLATES[doc.template].style;
  const overrides = Object.entries(doc.style || {}).filter(([, v]) => v !== null && v !== undefined);
  const thumbSource = isBlank(doc) ? SAMPLE : doc;

  // Store only real differences from the template, so switching templates
  // later restyles everything the user hasn't deliberately changed.
  const set = (key, value) => {
    const next = { ...(doc.style || {}) };
    if (JSON.stringify(preset[key]) === JSON.stringify(value)) delete next[key];
    else next[key] = value;
    onChange({ ...doc, style: next });
  };

  const chooseTemplate = (id) => onChange(withTemplate(doc, id));

  const order = style.section_order;
  const moveSection = (from, to) => set("section_order", moveItem(order, from, to));

  return (
    <div className="design-panel">
      <div className="design-ats-note">
        <strong>100% ATS-safe, whatever you pick.</strong> Every template is one column of real, selectable text
        with standard headings: no tables, text boxes, images or header/footer contact details.
      </div>

      <div className="template-filters" role="group" aria-label="Filter templates">
        {["All", ...CATEGORIES].map((c) => {
          const count = c === "All" ? TEMPLATE_IDS.length : TEMPLATE_IDS.filter((id) => TEMPLATES[id].category === c).length;
          return (
            <button key={c} type="button" className={`filter-chip${category === c ? " is-active" : ""}`}
              aria-pressed={category === c} onClick={() => setCategory(c)}>
              {c} <span>{count}</span>
            </button>
          );
        })}
      </div>

      <div className="template-gallery" role="radiogroup" aria-label="Template">
        {visible.map((id) => {
          const t = TEMPLATES[id];
          const selected = doc.template === id;
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={selected}
              className={`template-card${selected ? " is-selected" : ""}`}
              onClick={() => chooseTemplate(id)}
              title={t.tagline}
            >
              <ResumeThumbnail document={{ ...thumbSource, template: id, style: {} }} width={128} />
              <span className="template-card__name">{t.label}</span>
              <span className="template-card__credit">{t.inspired_by ? `LaTeX · ${t.inspired_by.split(" (")[0]}` : `${t.category} · original`}</span>
            </button>
          );
        })}
      </div>
      <p className="design-tagline">{TEMPLATES[doc.template].tagline}</p>

      <div className="design-head">
        <h3>Customize</h3>
        {overrides.length > 0 && (
          <button type="button" className="link-button" onClick={() => onChange({ ...doc, style: {} })}>
            Reset to {TEMPLATES[doc.template].label} defaults
          </button>
        )}
      </div>

      <fieldset className="design-group">
        <legend>Accent colour</legend>
        <div className="swatches">
          {ACCENT_SWATCHES.map((hex) => (
            <button key={hex} type="button" className={`swatch${style.accent.toUpperCase() === hex ? " is-active" : ""}`}
              style={{ background: hex }} aria-label={`Accent ${hex}`} aria-pressed={style.accent.toUpperCase() === hex}
              onClick={() => set("accent", hex)} />
          ))}
          <label className="swatch swatch--custom" title="Custom colour">
            <input type="color" value={style.accent.toLowerCase()} onChange={(e) => set("accent", e.target.value.toUpperCase())}
              aria-label="Custom accent colour" />
          </label>
        </div>
      </fieldset>

      <fieldset className="design-group">
        <legend>Typography</legend>
        <div className="design-field">
          <span className="field-label">Font</span>
          <div className="font-grid" role="radiogroup" aria-label="Font">
            {Object.entries(FONTS).map(([key, f]) => (
              <button key={key} type="button" role="radio" aria-checked={style.font === key}
                className={`font-option${style.font === key ? " is-active" : ""}`} style={{ fontFamily: FONT_CSS[key] }}
                onClick={() => set("font", key)}>
                <span className="font-option__sample">Aa</span> {f.label}
              </button>
            ))}
          </div>
        </div>
        <p className="field-hint">{FONTS[style.font].detail}. Word files use {FONTS[style.font].docx}.</p>
        <Slider label="Body size" value={style.font_size} min={8.5} max={12.5} step={0.5} unit=" pt" onChange={(v) => set("font_size", v)} />
        <Slider label="Name size" value={style.name_size} min={14} max={32} step={1} unit=" pt" onChange={(v) => set("name_size", v)} />
        <Slider label="Line spacing" value={style.line_height} min={1.1} max={1.8} step={0.05} unit="×" onChange={(v) => set("line_height", Math.round(v * 100) / 100)} />
      </fieldset>

      <fieldset className="design-group">
        <legend>Page</legend>
        <Segmented label="Paper" value={style.paper} onChange={(v) => set("paper", v)}
          options={[["a4", "A4"], ["letter", "US Letter"]]} />
        <Slider label="Margins" value={style.margin} min={8} max={30} step={1} unit=" mm" onChange={(v) => set("margin", v)} />
        <Segmented label="Header" value={style.header_align} onChange={(v) => set("header_align", v)}
          options={[["left", "Left"], ["center", "Centered"]]} />
        <Segmented label="Name" value={style.name_case} onChange={(v) => set("name_case", v)}
          options={[["normal", "As typed"], ["upper", "CAPITALS"]]} />
        <Segmented label="Headline colour" value={style.headline_color} onChange={(v) => set("headline_color", v)}
          options={[["text", "Text"], ["accent", "Accent"]]} />
        <Segmented label="Contact separator" value={style.contact_separator} onChange={(v) => set("contact_separator", v)}
          options={[["|", "a | b"], ["•", "a • b"], ["·", "a · b"]]} />
        <Segmented label="Dates" value={style.date_position} onChange={(v) => set("date_position", v)}
          options={[["right", "Right-aligned"], ["below", "Below the role"]]} />
        <Segmented label="Bullets" value={style.bullet} onChange={(v) => set("bullet", v)}
          options={[["•", "• Dot"], ["–", "– Dash"], ["›", "› Arrow"]]} />
      </fieldset>

      <fieldset className="design-group">
        <legend>Section headings</legend>
        <Segmented label="Style" value={style.heading_style} onChange={(v) => set("heading_style", v)}
          wrap options={[["rule", "Underline"], ["double", "Double rule"], ["short", "Short bar"], ["line", "Trailing line"], ["plain", "Plain"]]} />
        <Segmented label="Case" value={style.heading_case} onChange={(v) => set("heading_case", v)}
          options={[["upper", "UPPER"], ["smallcaps", "Small Caps", { fontVariant: "small-caps" }], ["normal", "Title"]]} />
        <Segmented label="Align" value={style.heading_align} onChange={(v) => set("heading_align", v)}
          options={[["left", "Left"], ["center", "Centered"]]} />
      </fieldset>

      <fieldset className="design-group">
        <legend>Section order</legend>
        <ol className="section-order">
          {order.map((key, i) => (
            <li key={key}>
              <span>{SECTION_TITLES[key]}</span>
              <span className="item-toolbar">
                <button type="button" className="icon-btn" onClick={() => moveSection(i, i - 1)} disabled={i === 0}
                  aria-label={`Move ${SECTION_TITLES[key]} up`}>↑</button>
                <button type="button" className="icon-btn" onClick={() => moveSection(i, i + 1)} disabled={i === order.length - 1}
                  aria-label={`Move ${SECTION_TITLES[key]} down`}>↓</button>
              </span>
            </li>
          ))}
        </ol>
        <p className="field-hint">Empty sections are left out of the file automatically.</p>
      </fieldset>
    </div>
  );
}
