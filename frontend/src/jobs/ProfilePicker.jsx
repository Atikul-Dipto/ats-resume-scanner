import { useRef, useState } from "react";
import { analyzeResume, resumes } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { isBlank, loadDraft } from "../builder/model.js";

// Chooses which resume the job list is ranked against.
export default function ProfilePicker({ profile, onChange }) {
  const { status } = useAuth();
  const [open, setOpen] = useState(!profile);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);
  const draft = loadDraft();
  const hasDraft = draft && !isBlank(draft.document);

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setOpen(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const pickDraft = () => run(async () => onChange({ kind: "draft", label: draft.title || "Builder draft", document: draft.document }));

  const pickSaved = (id) => run(async () => {
    const r = await resumes.get(id);
    onChange({ kind: "saved", label: r.title, document: r.document, resumeId: r.id });
  });

  const pickUpload = (file) => run(async () => {
    const result = await analyzeResume(file);
    onChange({ kind: "scan", label: file.name, document: result.draft_document });
  });

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && status === "authenticated" && saved === null) {
      resumes.list().then(setSaved).catch(() => setSaved([]));
    }
  }

  return (
    <div className="profile-picker hud-panel">
      <div className="profile-picker__current">
        {profile ? (
          <>
            <span className="profile-picker__label">Matching against</span>
            <strong>{profile.label}</strong>
          </>
        ) : (
          <>
            <strong>See which jobs fit your resume</strong>
            <span className="profile-picker__label">Pick a resume and every listing gets a match score and a skills gap.</span>
          </>
        )}
        <div className="profile-picker__actions">
          <button type="button" className="btn-ghost btn-small" onClick={toggle} aria-expanded={open}>
            {profile ? "Change resume" : open ? "Hide options" : "Choose resume"}
          </button>
          {profile && (
            <button type="button" className="btn-ghost btn-small" onClick={() => onChange(null)}>Stop matching</button>
          )}
        </div>
      </div>

      {open && (
        <div className="profile-picker__options">
          <button type="button" className="btn-small" disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? "Reading resume…" : "Upload resume (PDF/DOCX)"}
          </button>
          <input ref={fileRef} type="file" accept=".pdf,.docx" hidden
            onChange={(e) => e.target.files?.[0] && pickUpload(e.target.files[0])} />
          {hasDraft && (
            <button type="button" className="btn-ghost btn-small" disabled={busy} onClick={pickDraft}>
              Use builder draft “{draft.title || "My resume"}”
            </button>
          )}
          {status === "authenticated" && saved?.map((r) => (
            <button type="button" key={r.id} className="btn-ghost btn-small" disabled={busy} onClick={() => pickSaved(r.id)}>
              Saved: {r.title}
            </button>
          ))}
          {status !== "authenticated" && <span className="field-hint">Sign in to match against saved resumes.</span>}
          {error && <p className="error-text">⚠ {error}</p>}
          <p className="field-hint">Your file is only read to compute matches — it isn&apos;t stored, and nothing is shared with employers.</p>
        </div>
      )}
    </div>
  );
}
