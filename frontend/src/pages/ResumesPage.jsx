import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { auth as authApi, resumes } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { isBlank, loadDraft } from "../builder/model.js";
import StorageNotice from "../components/StorageNotice.jsx";

const tierOf = (score) => (score >= 80 ? "good" : score >= 55 ? "fair" : "poor");
const formatWhen = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

export default function ResumesPage() {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const draft = loadDraft();
  const hasDraft = draft && !isBlank(draft.document);

  const refresh = useCallback(() => {
    resumes.list().then(setItems).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (status === "anonymous") navigate("/login", { replace: true, state: { from: "/resumes" } });
    if (status === "authenticated") refresh();
  }, [status, navigate, refresh]);

  async function act(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const createBlank = () => act(async () => {
    const created = await resumes.create("Untitled resume");
    navigate(`/builder/${created.id}`);
  });

  const saveDraftToAccount = () => act(async () => {
    const created = await resumes.create(draft.title || "My resume", draft.document, draft.jobDescription);
    navigate(`/builder/${created.id}`);
  });

  const remove = (resume) => act(async () => {
    if (!window.confirm(`Delete “${resume.title}”? This can't be undone.`)) return;
    await resumes.remove(resume.id);
    refresh();
  });

  const duplicate = (resume) => act(async () => {
    await resumes.duplicate(resume.id);
    refresh();
  });

  const deleteAccount = () => act(async () => {
    if (!window.confirm("Delete your account and every saved resume? This can't be undone.")) return;
    await authApi.deleteAccount();
    logout();
    navigate("/");
  });

  if (status !== "authenticated") return <div className="hud-panel page-message">Checking your session…</div>;

  return (
    <div className="resumes-page">
      <header className="app-header">
        <p className="app-eyebrow">// SAVED RESUMES</p>
        <h1>My resumes</h1>
        <p>Signed in as {user.email}. Keep one resume per target role and tailor each to its job description.</p>
      </header>

      <StorageNotice />
      <div className="resumes-actions">
        <button type="button" onClick={createBlank} disabled={busy}>+ New resume</button>
        {hasDraft && (
          <button type="button" className="btn-ghost" onClick={saveDraftToAccount} disabled={busy}>
            Save browser draft “{draft.title || "My resume"}”
          </button>
        )}
      </div>

      {error && <p className="error-text">⚠ {error}</p>}
      {items === null && !error && <p className="no-issues">Loading…</p>}
      {items?.length === 0 && (
        <div className="hud-panel page-message">
          No saved resumes yet. Start one above, or <Link to="/">scan an existing resume</Link> and open it in the builder.
        </div>
      )}

      {items?.length > 0 && (
        <ul className="resume-list">
          {items.map((r) => (
            <li key={r.id} className="resume-card hud-panel">
              <Link to={`/builder/${r.id}`} className="resume-card__main">
                <span className={`resume-card__score tier-${tierOf(r.last_score ?? 0)}`}>
                  {r.last_score != null ? Math.round(r.last_score) : "–"}
                </span>
                <span>
                  <strong>{r.title}</strong>
                  <span className="resume-card__meta">Edited {formatWhen(r.updated_at)} · v{r.version}</span>
                </span>
              </Link>
              <div className="resume-card__actions">
                <button type="button" className="btn-ghost btn-small" onClick={() => duplicate(r)} disabled={busy}>Duplicate</button>
                <button type="button" className="btn-ghost btn-small btn-danger" onClick={() => remove(r)} disabled={busy}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="danger-zone">
        <button type="button" className="link-button" onClick={deleteAccount} disabled={busy}>Delete my account</button>
        {" "}— removes your account, every saved resume and its score history.
      </p>
    </div>
  );
}
