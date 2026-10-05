// Client-side helpers for the ResumeDocument shape defined in
// backend/app/schemas/resume.py. The backend is the source of truth for
// validation and scoring; this file only builds, edits and previews it.

const DRAFT_KEY = "ats-builder-draft-v1";

let keySeq = 0;
export const newKey = () => `k${Date.now().toString(36)}${(keySeq++).toString(36)}`;

export const emptyExperience = () => ({ _key: newKey(), title: "", company: "", location: "", start: "", end: "", current: false, bullets: [""] });
export const emptyEducation = () => ({ _key: newKey(), institution: "", degree: "", location: "", start: "", end: "", details: [] });
export const emptySkillGroup = () => ({ _key: newKey(), name: "", skills: [] });
export const emptyProject = () => ({ _key: newKey(), name: "", url: "", bullets: [""] });
export const emptyCertification = () => ({ _key: newKey(), name: "", issuer: "", date: "" });
export const emptyLink = () => ({ _key: newKey(), label: "", url: "" });

export function emptyDocument() {
  return {
    schema_version: 1,
    template: "classic",
    basics: { name: "", headline: "", email: "", phone: "", location: "", links: [], summary: "" },
    experience: [emptyExperience()],
    education: [emptyEducation()],
    skills: [emptySkillGroup()],
    projects: [],
    certifications: [],
  };
}

const LIST_KEYS = ["experience", "education", "skills", "projects", "certifications"];

// The API strips unknown fields, so React keys are re-attached on every load.
export function withKeys(doc) {
  const base = emptyDocument();
  const out = { ...base, ...doc, basics: { ...base.basics, ...(doc?.basics || {}) } };
  out.basics.links = (out.basics.links || []).map((l) => ({ ...l, _key: l._key || newKey() }));
  for (const key of LIST_KEYS) {
    out[key] = (doc?.[key] || []).map((item) => ({ ...item, _key: item._key || newKey() }));
  }
  return out;
}

export function isBlank(doc) {
  const b = doc.basics;
  const hasBasics = [b.name, b.headline, b.email, b.phone, b.summary].some((v) => v?.trim());
  const hasItems = doc.experience.some((e) => e.title || e.company || e.bullets.some(Boolean));
  return !hasBasics && !hasItems;
}

// --- immutable updates by path, e.g. setIn(doc, ["experience", 0, "title"], "Analyst")
export function setIn(obj, [head, ...rest], value) {
  const next = Array.isArray(obj) ? [...obj] : { ...obj };
  next[head] = rest.length ? setIn(obj[head], rest, value) : value;
  return next;
}

export function getIn(obj, path) {
  return path.reduce((acc, key) => acc?.[key], obj);
}

export function moveItem(list, from, to) {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

// --- local draft (anonymous users, and unsaved work before sign-in)
export function loadDraft() {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return { document: withKeys(parsed.document), jobDescription: parsed.jobDescription || "", title: parsed.title || "" };
  } catch {
    return null;
  }
}

export function saveDraft(draft) {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* storage full or unavailable — drafting still works for this session */
  }
}

export function clearDraft() {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

// --- preview layout: mirrors build_blocks() in backend/app/builder/layout.py
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatDate(value) {
  if (!value) return "";
  const [year, month] = value.split("-");
  return month ? `${MONTHS[Number(month) - 1]} ${year}` : year;
}

export function formatRange(start, end, current = false) {
  const s = formatDate(start);
  const e = current ? "Present" : formatDate(end);
  return s && e ? `${s} – ${e}` : s || e;
}

const join = (parts, sep = " | ") => parts.filter(Boolean).join(sep);

export function buildBlocks(doc) {
  const blocks = [];
  const b = doc.basics;
  if (b.name) blocks.push(["name", b.name]);
  if (b.headline) blocks.push(["headline", b.headline]);
  const contact = join([b.email, b.phone, b.location, ...b.links.map((l) => l.url)]);
  if (contact) blocks.push(["contact", contact]);

  if (b.summary?.trim()) {
    blocks.push(["heading", "Summary"]);
    b.summary.split("\n").filter((p) => p.trim()).forEach((p) => blocks.push(["line", p]));
  }

  const exp = doc.experience.filter((e) => e.title || e.company || e.bullets.some(Boolean));
  if (exp.length) {
    blocks.push(["heading", "Experience"]);
    for (const e of exp) {
      blocks.push(["entry_title", join([e.title, e.company], ", ")]);
      const meta = join([formatRange(e.start, e.end, e.current), e.location]);
      if (meta) blocks.push(["entry_meta", meta]);
      e.bullets.filter(Boolean).forEach((t) => blocks.push(["bullet", t]));
    }
  }

  const edu = doc.education.filter((e) => e.institution || e.degree);
  if (edu.length) {
    blocks.push(["heading", "Education"]);
    for (const e of edu) {
      blocks.push(["entry_title", join([e.degree, e.institution], ", ")]);
      const meta = join([formatRange(e.start, e.end), e.location]);
      if (meta) blocks.push(["entry_meta", meta]);
      e.details.filter(Boolean).forEach((t) => blocks.push(["line", t]));
    }
  }

  const groups = doc.skills.filter((g) => g.skills.some(Boolean));
  if (groups.length) {
    blocks.push(["heading", "Skills"]);
    for (const g of groups) {
      const listed = g.skills.filter(Boolean).join(", ");
      blocks.push(["line", g.name ? `${g.name}: ${listed}` : listed]);
    }
  }

  const projects = doc.projects.filter((p) => p.name || p.bullets.some(Boolean));
  if (projects.length) {
    blocks.push(["heading", "Projects"]);
    for (const p of projects) {
      blocks.push(["entry_title", join([p.name, p.url])]);
      p.bullets.filter(Boolean).forEach((t) => blocks.push(["bullet", t]));
    }
  }

  const certs = doc.certifications.filter((c) => c.name);
  if (certs.length) {
    blocks.push(["heading", "Certifications"]);
    certs.forEach((c) => blocks.push(["line", join([c.name, c.issuer, formatDate(c.date)])]));
  }
  return blocks;
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
