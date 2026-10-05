export const DISCIPLINES = {
  data: "Data & Analytics",
  software: "Software & IT",
  civil: "Civil & Construction",
  electrical: "Electrical & Electronics",
  mechanical: "Mechanical, Industrial & Textile",
};

export const WORKPLACES = { onsite: "On-site", remote: "Remote", hybrid: "Hybrid" };
export const EMPLOYMENT_TYPES = { full_time: "Full-time", part_time: "Part-time", contract: "Contract", internship: "Internship" };
const SOURCE_NAMES = { remotive: "Remotive", arbeitnow: "Arbeitnow", themuse: "The Muse", adzuna: "Adzuna" };
// Ingested sources are "<kind>:<name>" (see backend/app/ingest/models.py).
const SOURCE_KINDS = { gh: "company careers", lv: "company careers", ab: "company careers", sr: "company careers",
  ld: "company careers", web: "job board" };

export function sourceLabel(source) {
  if (source === "local") return "Posted here";
  const [kind] = source.split(":");
  if (source.includes(":")) return `via ${SOURCE_KINDS[kind] || "partner site"}`;
  return `via ${SOURCE_NAMES[source] || source}`;
}

export function formatSalary(job) {
  const { salary_min: min, salary_max: max, salary_currency: cur, salary_period: period } = job;
  if (min == null && max == null) return null;
  const fmt = (n) => (cur === "BDT" ? `৳${n.toLocaleString("en-IN")}` : `${cur} ${n.toLocaleString()}`);
  const range = min != null && max != null ? `${fmt(min)}–${fmt(max)}` : min != null ? `from ${fmt(min)}` : `up to ${fmt(max)}`;
  return `${range} / ${period}`;
}

export function formatExperience(job) {
  const { experience_min: min, experience_max: max } = job;
  if (min == null && max == null) return null;
  if (min != null && max != null) return `${min}–${max} yrs`;
  return min != null ? `${min}+ yrs` : `up to ${max} yrs`;
}

export function formatDeadline(deadline) {
  if (!deadline) return null;
  const days = Math.ceil((new Date(`${deadline}T23:59:59`) - new Date()) / 86400000);
  const date = new Date(`${deadline}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return days <= 3 ? `Closes ${date} (${days <= 0 ? "today" : `${days}d left`})` : `Apply by ${date}`;
}

export const matchTier = (score) => (score >= 70 ? "good" : score >= 40 ? "fair" : "poor");
export const matchLabel = (score) => (score >= 70 ? "Strong match" : score >= 40 ? "Partial match" : "Low match");

// Defense in depth: the API already rejects anything else.
export const safeHref = (url) => (/^(https?:\/\/|mailto:)/i.test(url || "") ? url : null);

// The resume being matched survives navigation to a job and back.
const PROFILE_KEY = "ats-jobs-profile-v1";
export function loadProfile() {
  try {
    return JSON.parse(window.sessionStorage.getItem(PROFILE_KEY)) || null;
  } catch {
    return null;
  }
}
export function saveProfile(profile) {
  try {
    if (profile) window.sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    else window.sessionStorage.removeItem(PROFILE_KEY);
  } catch {
    /* storage unavailable */
  }
}
