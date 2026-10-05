import { useId, useState } from "react";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function TextField({ label, value, onChange, placeholder, type = "text", wide = false, hint }) {
  const id = useId();
  return (
    <div className={`field ${wide ? "field--wide" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <input id={id} type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

export function TextArea({ label, value, onChange, placeholder, rows = 3, hint }) {
  const id = useId();
  return (
    <div className="field field--wide">
      <label htmlFor={id}>{label}</label>
      <textarea id={id} rows={rows} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

// "YYYY" or "YYYY-MM" (matches the API's date format). Month is optional
// because imported resumes often only have years.
export function DateField({ label, value, onChange, disabled = false }) {
  const id = useId();
  const [year = "", month = ""] = (value || "").split("-");
  // While focused, show what's being typed ("20"); otherwise the stored year.
  const [draftYear, setDraftYear] = useState(null);

  const emit = (y, m) => onChange(/^\d{4}$/.test(y) ? (m ? `${y}-${m}` : y) : "");

  return (
    <div className="field field--date">
      <label htmlFor={id}>{label}</label>
      <div className="date-inputs">
        <select
          aria-label={`${label} month`}
          value={month}
          disabled={disabled}
          onChange={(e) => emit(year, e.target.value)}
        >
          <option value="">Month</option>
          {MONTHS.map((m, i) => (
            <option key={m} value={String(i + 1).padStart(2, "0")}>{m}</option>
          ))}
        </select>
        <input
          id={id}
          type="text"
          inputMode="numeric"
          maxLength={4}
          placeholder="Year"
          disabled={disabled}
          value={draftYear ?? year}
          onFocus={() => setDraftYear(year)}
          onBlur={() => setDraftYear(null)}
          onChange={(e) => {
            const y = e.target.value.replace(/\D/g, "").slice(0, 4);
            setDraftYear(y);
            if (y.length === 4 || y.length === 0) emit(y, month);
          }}
        />
      </div>
    </div>
  );
}

export function ItemToolbar({ index, count, onMove, onRemove, label }) {
  return (
    <div className="item-toolbar">
      <button type="button" className="icon-btn" onClick={() => onMove(index - 1)} disabled={index === 0}
        aria-label={`Move ${label} up`} title="Move up">↑</button>
      <button type="button" className="icon-btn" onClick={() => onMove(index + 1)} disabled={index === count - 1}
        aria-label={`Move ${label} down`} title="Move down">↓</button>
      <button type="button" className="icon-btn icon-btn--danger" onClick={onRemove}
        aria-label={`Remove ${label}`} title="Remove">✕</button>
    </div>
  );
}

// Matches the server's flagged-line snippets (truncated to 140 chars) back to bullets.
function reasonsFor(text, flaggedLines) {
  if (!text?.trim() || !flaggedLines) return null;
  const match = flaggedLines.find((f) => {
    const snippet = f.text.endsWith("...") ? f.text.slice(0, -3) : f.text;
    return text.trim().startsWith(snippet);
  });
  return match?.reasons || null;
}

export function BulletList({ label, items, onChange, flaggedLines, placeholder, max = 15, asBullets = true }) {
  const update = (i, value) => onChange(items.map((item, j) => (j === i ? value : item)));
  const remove = (i) => onChange(items.filter((_, j) => j !== i));

  return (
    <div className="field field--wide bullet-list">
      <span className="field-label">{label}</span>
      {items.map((item, i) => {
        const reasons = asBullets ? reasonsFor(item, flaggedLines) : null;
        return (
          <div className="bullet-row" key={i}>
            <span className="bullet-glyph" aria-hidden="true">{asBullets ? "•" : "–"}</span>
            <div className="bullet-input">
              <textarea
                rows={2}
                value={item}
                placeholder={placeholder}
                aria-label={`${label} ${i + 1}`}
                onChange={(e) => update(i, e.target.value.replace(/\n/g, " "))}
              />
              {reasons && (
                <p className="bullet-coach">
                  {reasons.map((r) => (
                    <span key={r}>{r}</span>
                  ))}
                </p>
              )}
            </div>
            <button type="button" className="icon-btn icon-btn--danger" onClick={() => remove(i)}
              aria-label={`Remove ${label} ${i + 1}`}>✕</button>
          </div>
        );
      })}
      {items.length < max && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...items, ""])}>
          + Add {asBullets ? "bullet" : "line"}
        </button>
      )}
    </div>
  );
}

export function ChipInput({ label, values, onChange, placeholder, max = 60 }) {
  const id = useId();
  const [draft, setDraft] = useState("");

  const commit = (raw) => {
    const additions = raw.split(",").map((s) => s.trim()).filter(Boolean);
    if (!additions.length) return;
    const lower = new Set(values.map((v) => v.toLowerCase()));
    const merged = [...values];
    for (const a of additions) {
      if (!lower.has(a.toLowerCase()) && merged.length < max) {
        merged.push(a);
        lower.add(a.toLowerCase());
      }
    }
    onChange(merged);
    setDraft("");
  };

  return (
    <div className="field field--wide">
      <label htmlFor={id}>{label}</label>
      <div className="chip-input">
        {values.map((v, i) => (
          <span className="chip chip-matched chip--removable" key={`${v}-${i}`}>
            {v}
            <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(values.filter((_, j) => j !== i))}>
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={draft}
          placeholder={values.length ? "" : placeholder}
          onChange={(e) => {
            const v = e.target.value;
            if (v.includes(",")) commit(v);
            else setDraft(v);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit(draft);
            } else if (e.key === "Backspace" && !draft && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
          onBlur={() => commit(draft)}
        />
      </div>
      <p className="field-hint">Press Enter or comma to add.</p>
    </div>
  );
}
