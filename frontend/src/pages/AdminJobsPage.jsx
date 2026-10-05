import { useCallback, useEffect, useState } from "react";
import { adminJobs } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ChipInput } from "../builder/fields.jsx";
import { DISCIPLINES, EMPLOYMENT_TYPES, WORKPLACES, sourceLabel } from "../jobs/format.js";
import StorageNotice from "../components/StorageNotice.jsx";

const EMPTY = {
  title: "", company: "", location: "", discipline: "data", employment_type: "full_time", workplace: "onsite",
  experience_min: "", experience_max: "", salary_min: "", salary_max: "", salary_currency: "BDT", salary_period: "month",
  description: "", skills: [], apply_url: "", deadline: "", status: "published",
};

const numOrNull = (v) => (v === "" || v == null ? null : Number(v));

function toPayload(form) {
  return {
    ...form,
    experience_min: numOrNull(form.experience_min),
    experience_max: numOrNull(form.experience_max),
    salary_min: numOrNull(form.salary_min),
    salary_max: numOrNull(form.salary_max),
    deadline: form.deadline || null,
  };
}

function fromJob(job) {
  const form = { ...EMPTY };
  for (const key of Object.keys(EMPTY)) form[key] = job[key] ?? EMPTY[key];
  return form;
}

function JobForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave(toPayload(form));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const field = (label, key, props = {}) => (
    <label className="field">
      <span className="field-label">{label}</span>
      <input type="text" value={form[key]} onChange={set(key)} {...props} />
    </label>
  );
  const select = (label, key, options) => (
    <label className="field">
      <span className="field-label">{label}</span>
      <select value={form[key]} onChange={set(key)}>
        {Object.entries(options).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
    </label>
  );

  return (
    <form className="admin-form hud-panel" onSubmit={submit}>
      <div className="field-grid">
        {field("Job title *", "title", { required: true, minLength: 2, maxLength: 300, placeholder: "Junior Data Analyst" })}
        {field("Company *", "company", { required: true, maxLength: 300 })}
        {field("Location", "location", { maxLength: 200, placeholder: "Dhaka / Chattogram / Remote" })}
        {select("Discipline *", "discipline", DISCIPLINES)}
        {select("Employment type", "employment_type", EMPLOYMENT_TYPES)}
        {select("Workplace", "workplace", WORKPLACES)}
        {field("Min experience (yrs)", "experience_min", { type: "number", min: 0, max: 50, step: 0.5 })}
        {field("Max experience (yrs)", "experience_max", { type: "number", min: 0, max: 50, step: 0.5 })}
        {field("Min salary", "salary_min", { type: "number", min: 0 })}
        {field("Max salary", "salary_max", { type: "number", min: 0 })}
        {field("Currency", "salary_currency", { maxLength: 3 })}
        {select("Salary period", "salary_period", { month: "per month", year: "per year" })}
        {field("Application deadline", "deadline", { type: "date" })}
        {field("Apply link (https:// or mailto:)", "apply_url", { maxLength: 500, placeholder: "https://company.com/careers/123" })}
        {select("Status", "status", { published: "Published", draft: "Draft", closed: "Closed" })}
      </div>
      <ChipInput label="Required skills (matching uses these first)" values={form.skills} onChange={set("skills")}
        placeholder="AutoCAD, STAAD Pro, Estimation" max={40} />
      <label className="field field--wide">
        <span className="field-label">Description * (responsibilities, requirements, benefits)</span>
        <textarea rows={10} required minLength={20} maxLength={20000} value={form.description} onChange={set("description")} />
        <span className="field-hint">Skills mentioned here are detected automatically and added to matching.</span>
      </label>
      {error && <p className="error-text">⚠ {error}</p>}
      <div className="admin-form__actions">
        <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save job"}</button>
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export default function AdminJobsPage() {
  const { user, status } = useAuth();
  const [source, setSource] = useState("local");
  const [statusFilter, setStatusFilter] = useState("");
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null); // null | "new" | job
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(() => {
    adminJobs
      .list({ source, status: statusFilter || null, page_size: 100 })
      .then(setData)
      .catch((err) => setError(err.message));
  }, [source, statusFilter]);

  useEffect(() => {
    if (user?.is_admin) refresh();
  }, [user, refresh]);

  if (status === "checking") return <div className="hud-panel page-message">Checking your session…</div>;
  if (!user?.is_admin) {
    return <div className="hud-panel page-message">Admin access required. Admins are configured on the server with ADMIN_EMAILS.</div>;
  }

  async function act(fn, done) {
    setError(null);
    setMessage(null);
    try {
      await fn();
      if (done) setMessage(done);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function save(payload) {
    if (editing === "new") await adminJobs.create(payload);
    else await adminJobs.update(editing.id, payload);
    setEditing(null);
    setMessage("Job saved.");
    refresh();
  }

  const sync = () => act(async () => {
    const stats = await adminJobs.sync();
    setMessage(`Remote sync: ${stats.created} new, ${stats.updated} updated, ${stats.skipped} skipped, ${stats.expired} expired.`);
  });

  return (
    <div className="admin-page">
      <header className="app-header">
        <p className="app-eyebrow">Admin</p>
        <h1>Manage job listings</h1>
        <p>Post local jobs, hide imported ones, and refresh the remote catalog.</p>
      </header>

      <StorageNotice />
      <div className="admin-toolbar hud-panel">
        <div className="discipline-chips">
          <button type="button" className={`filter-chip ${source === "local" ? "is-active" : ""}`} onClick={() => setSource("local")}>Posted here</button>
          <button type="button" className={`filter-chip ${source === "remote" ? "is-active" : ""}`} onClick={() => setSource("remote")}>Imported</button>
        </div>
        <select aria-label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Any status</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="closed">Closed / hidden</option>
        </select>
        <div className="builder-actions">
          <button type="button" className="btn-ghost btn-small" onClick={sync}>Sync remote jobs now</button>
          <button type="button" className="btn-small" onClick={() => setEditing("new")}>+ Post a job</button>
        </div>
      </div>

      {message && <p className="success-text">✓ {message}</p>}
      {error && <p className="error-text">⚠ {error}</p>}

      {editing && (
        <JobForm key={editing === "new" ? "new" : editing.id} initial={editing === "new" ? EMPTY : fromJob(editing)}
          onSave={save} onCancel={() => setEditing(null)} />
      )}

      {data && (
        <>
          <p className="jobs-count">{data.total} job{data.total === 1 ? "" : "s"}</p>
          <ul className="resume-list">
            {data.items.map((job) => (
              <li key={job.id} className="resume-card hud-panel">
                <div className="resume-card__main">
                  <span className={`status-pill status-pill--${job.status}`}>{job.status}</span>
                  <span>
                    <strong>{job.title}</strong>
                    <span className="resume-card__meta">
                      {job.company} · {DISCIPLINES[job.discipline]} · {sourceLabel(job.source)}
                      {job.deadline && ` · deadline ${job.deadline}`}
                    </span>
                  </span>
                </div>
                <div className="resume-card__actions">
                  {job.source === "local" && (
                    <button type="button" className="btn-ghost btn-small" onClick={() => setEditing(job)}>Edit</button>
                  )}
                  {job.status === "published" ? (
                    <button type="button" className="btn-ghost btn-small" onClick={() => act(() => adminJobs.setStatus(job.id, "closed"), "Job hidden.")}>
                      {job.source === "local" ? "Close" : "Hide"}
                    </button>
                  ) : (
                    <button type="button" className="btn-ghost btn-small" onClick={() => act(() => adminJobs.setStatus(job.id, "published"), "Job published.")}>
                      Publish
                    </button>
                  )}
                  {job.source === "local" && (
                    <button type="button" className="btn-ghost btn-small btn-danger" onClick={() => {
                      if (window.confirm(`Delete “${job.title}”?`)) act(() => adminJobs.remove(job.id), "Job deleted.");
                    }}>Delete</button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
