import { useState } from "react";
import { BulletList, ChipInput, DateField, ItemToolbar, TextArea, TextField } from "./fields.jsx";
import {
  emptyCertification,
  emptyEducation,
  emptyExperience,
  emptyLink,
  emptyProject,
  emptySkillGroup,
  moveItem,
} from "./model.js";

export function SectionCard({ title, icon, count, children, defaultOpen = true, action, onToggle, className = "" }) {
  const [open, setOpen] = useState(defaultOpen);
  const toggle = () => {
    setOpen(!open);
    onToggle?.(!open);
  };
  return (
    <section className={`editor-card ${open ? "is-open" : ""} ${className}`}>
      <header className="editor-card__head">
        <button type="button" className="editor-card__toggle" onClick={toggle} aria-expanded={open}>
          <span className="section-icon">{icon}</span>
          {title}
          {count != null && <span className="editor-card__count">{count}</span>}
          <span className="editor-card__chevron" aria-hidden="true">{open ? "▾" : "▸"}</span>
        </button>
        {open && action}
      </header>
      {open && <div className="editor-card__body">{children}</div>}
    </section>
  );
}

// Shared list mechanics for experience/education/projects/... sections.
function useList(items, onChange) {
  return {
    update: (i, patch) => onChange(items.map((item, j) => (j === i ? { ...item, ...patch } : item))),
    remove: (i) => onChange(items.filter((_, j) => j !== i)),
    move: (from, to) => onChange(moveItem(items, from, to)),
  };
}

export function BasicsEditor({ basics, onChange }) {
  const set = (key) => (value) => onChange({ ...basics, [key]: value });
  const links = useList(basics.links, (next) => onChange({ ...basics, links: next }));

  return (
    <SectionCard title="Contact & headline" icon="◎">
      <div className="field-grid">
        <TextField label="Full name" value={basics.name} onChange={set("name")} placeholder="Jane Doe" />
        <TextField label="Headline" value={basics.headline} onChange={set("headline")} placeholder="Data Analyst" />
        <TextField label="Email" type="email" value={basics.email} onChange={set("email")} placeholder="jane@example.com" />
        <TextField label="Phone" type="tel" value={basics.phone} onChange={set("phone")} placeholder="+880 1XXX-XXXXXX" />
        <TextField label="Location" value={basics.location} onChange={set("location")} placeholder="Dhaka, Bangladesh" wide />
      </div>
      {basics.links.map((link, i) => (
        <div className="link-row" key={link._key}>
          <TextField label={`Link ${i + 1}`} value={link.url} onChange={(url) => links.update(i, { url })}
            placeholder="linkedin.com/in/janedoe" wide />
          <button type="button" className="icon-btn icon-btn--danger" onClick={() => links.remove(i)} aria-label={`Remove link ${i + 1}`}>✕</button>
        </div>
      ))}
      {basics.links.length < 6 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange({ ...basics, links: [...basics.links, emptyLink()] })}>
          + Add link (LinkedIn, GitHub, portfolio)
        </button>
      )}
      <TextArea label="Professional summary" value={basics.summary} onChange={set("summary")} rows={4}
        placeholder="2–3 sentences: who you are, what you're best at, and the role you're targeting."
        hint={`${basics.summary.length}/2000`} />
    </SectionCard>
  );
}

export function ExperienceEditor({ items, onChange, flaggedLines }) {
  const list = useList(items, onChange);
  return (
    <SectionCard title="Experience" icon="▣" count={items.length}
      action={items.length < 20 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...items, emptyExperience()])}>+ Add role</button>
      )}>
      {items.length === 0 && <p className="no-issues">No roles yet — add your most recent one first.</p>}
      {items.map((item, i) => {
        const label = [item.title, item.company].filter(Boolean).join(" at ") || `Role ${i + 1}`;
        return (
          <div className="editor-item" key={item._key}>
            <div className="editor-item__head">
              <strong>{label}</strong>
              <ItemToolbar index={i} count={items.length} label={label} onMove={(to) => list.move(i, to)} onRemove={() => list.remove(i)} />
            </div>
            <div className="field-grid">
              <TextField label="Job title" value={item.title} onChange={(title) => list.update(i, { title })} placeholder="Data Analyst" />
              <TextField label="Company" value={item.company} onChange={(company) => list.update(i, { company })} placeholder="Acme Corp" />
              <DateField label="Start" value={item.start} onChange={(start) => list.update(i, { start })} />
              <DateField label="End" value={item.current ? "" : item.end} disabled={item.current} onChange={(end) => list.update(i, { end })} />
              <label className="checkbox-field">
                <input type="checkbox" checked={item.current} onChange={(e) => list.update(i, { current: e.target.checked, end: "" })} />
                I currently work here
              </label>
              <TextField label="Location" value={item.location} onChange={(location) => list.update(i, { location })} placeholder="Dhaka / Remote" />
            </div>
            <BulletList label="Achievements" items={item.bullets} onChange={(bullets) => list.update(i, { bullets })}
              flaggedLines={flaggedLines}
              placeholder="Start with an action verb and include a number: “Cut report latency 40% by…”" />
          </div>
        );
      })}
    </SectionCard>
  );
}

export function EducationEditor({ items, onChange }) {
  const list = useList(items, onChange);
  return (
    <SectionCard title="Education" icon="◈" count={items.length}
      action={items.length < 10 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...items, emptyEducation()])}>+ Add school</button>
      )}>
      {items.map((item, i) => {
        const label = item.degree || item.institution || `Education ${i + 1}`;
        return (
          <div className="editor-item" key={item._key}>
            <div className="editor-item__head">
              <strong>{label}</strong>
              <ItemToolbar index={i} count={items.length} label={label} onMove={(to) => list.move(i, to)} onRemove={() => list.remove(i)} />
            </div>
            <div className="field-grid">
              <TextField label="Degree" value={item.degree} onChange={(degree) => list.update(i, { degree })} placeholder="BSc Computer Science" />
              <TextField label="Institution" value={item.institution} onChange={(institution) => list.update(i, { institution })} placeholder="University of Dhaka" />
              <DateField label="Start" value={item.start} onChange={(start) => list.update(i, { start })} />
              <DateField label="End" value={item.end} onChange={(end) => list.update(i, { end })} />
            </div>
            <BulletList label="Details" asBullets={false} items={item.details} onChange={(details) => list.update(i, { details })}
              placeholder="GPA, honors, relevant coursework" max={15} />
          </div>
        );
      })}
    </SectionCard>
  );
}

export function SkillsEditor({ groups, onChange, missingKeywords }) {
  const list = useList(groups, onChange);
  const addKeyword = (kw) => {
    if (!groups.length) return onChange([{ ...emptySkillGroup(), skills: [kw] }]);
    list.update(0, { skills: [...groups[0].skills, kw] });
  };

  return (
    <SectionCard title="Skills" icon="#" count={groups.reduce((n, g) => n + g.skills.length, 0)}
      action={groups.length < 10 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...groups, emptySkillGroup()])}>+ Add group</button>
      )}>
      {missingKeywords?.length > 0 && (
        <div className="keyword-suggest">
          <p className="field-hint">From the target job — add the ones you genuinely have:</p>
          <div className="chip-list">
            {missingKeywords.slice(0, 12).map((kw) => (
              <button type="button" key={kw} className="chip chip-missing chip--action" onClick={() => addKeyword(kw)}>
                + {kw}
              </button>
            ))}
          </div>
        </div>
      )}
      {groups.map((group, i) => (
        <div className="editor-item" key={group._key}>
          <div className="editor-item__head">
            <TextField label="Group name (optional)" value={group.name} onChange={(name) => list.update(i, { name })} placeholder="Languages, Tools…" />
            <ItemToolbar index={i} count={groups.length} label={group.name || `skill group ${i + 1}`} onMove={(to) => list.move(i, to)} onRemove={() => list.remove(i)} />
          </div>
          <ChipInput label="Skills" values={group.skills} onChange={(skills) => list.update(i, { skills })} placeholder="Python, SQL, Power BI" />
        </div>
      ))}
    </SectionCard>
  );
}

export function ProjectsEditor({ items, onChange, flaggedLines }) {
  const list = useList(items, onChange);
  return (
    <SectionCard title="Projects" icon="◇" count={items.length} defaultOpen={items.length > 0}
      action={items.length < 15 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...items, emptyProject()])}>+ Add project</button>
      )}>
      {items.length === 0 && <p className="no-issues">Optional — great for early-career or career-switch resumes.</p>}
      {items.map((item, i) => (
        <div className="editor-item" key={item._key}>
          <div className="editor-item__head">
            <strong>{item.name || `Project ${i + 1}`}</strong>
            <ItemToolbar index={i} count={items.length} label={item.name || `project ${i + 1}`} onMove={(to) => list.move(i, to)} onRemove={() => list.remove(i)} />
          </div>
          <div className="field-grid">
            <TextField label="Name" value={item.name} onChange={(name) => list.update(i, { name })} placeholder="Sales forecasting dashboard" />
            <TextField label="Link" value={item.url} onChange={(url) => list.update(i, { url })} placeholder="github.com/you/project" />
          </div>
          <BulletList label="What you did" items={item.bullets} onChange={(bullets) => list.update(i, { bullets })} flaggedLines={flaggedLines} />
        </div>
      ))}
    </SectionCard>
  );
}

export function CertificationsEditor({ items, onChange }) {
  const list = useList(items, onChange);
  return (
    <SectionCard title="Certifications" icon="✦" count={items.length} defaultOpen={items.length > 0}
      action={items.length < 20 && (
        <button type="button" className="btn-ghost btn-small" onClick={() => onChange([...items, emptyCertification()])}>+ Add certification</button>
      )}>
      {items.length === 0 && <p className="no-issues">Optional.</p>}
      {items.map((item, i) => (
        <div className="editor-item editor-item--inline" key={item._key}>
          <div className="field-grid field-grid--3">
            <TextField label="Name" value={item.name} onChange={(name) => list.update(i, { name })} placeholder="Google Data Analytics" />
            <TextField label="Issuer" value={item.issuer} onChange={(issuer) => list.update(i, { issuer })} placeholder="Google" />
            <DateField label="Date" value={item.date} onChange={(date) => list.update(i, { date })} />
          </div>
          <ItemToolbar index={i} count={items.length} label={item.name || `certification ${i + 1}`} onMove={(to) => list.move(i, to)} onRemove={() => list.remove(i)} />
        </div>
      ))}
    </SectionCard>
  );
}
