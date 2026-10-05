import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { exportDocument, resumes } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import ResumePreview from "../builder/ResumePreview.jsx";
import ScorePanel from "../builder/ScorePanel.jsx";
import {
  BasicsEditor,
  CertificationsEditor,
  EducationEditor,
  ExperienceEditor,
  ProjectsEditor,
  SkillsEditor,
} from "../builder/SectionEditors.jsx";
import { clearDraft, downloadBlob, emptyDocument, loadDraft, saveDraft, withKeys } from "../builder/model.js";
import useLiveScore from "../builder/useLiveScore.js";

const snapshotOf = (title, doc, jd) => JSON.stringify([title, doc, jd]);

export default function BuilderPage() {
  const { id } = useParams(); // undefined = local draft, no account needed
  const location = useLocation();
  const navigate = useNavigate();
  const { status: authStatus } = useAuth();

  const [doc, setDoc] = useState(null);
  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [saved, setSaved] = useState(null); // { version, snapshot } for account-backed resumes
  const [loadError, setLoadError] = useState(null);
  const [saveState, setSaveState] = useState({ status: "idle", message: null });
  const [imported, setImported] = useState(false);
  const [tab, setTab] = useState("score");
  const [exporting, setExporting] = useState(null);

  const loadSaved = useCallback(() => {
    setLoadError(null);
    return resumes
      .get(id)
      .then((r) => {
        const keyed = withKeys(r.document);
        const jdText = r.target_job_description || "";
        setDoc(keyed);
        setTitle(r.title);
        setJd(jdText);
        setSaved({ version: r.version, snapshot: snapshotOf(r.title, keyed, jdText) });
        setSaveState({ status: "idle", message: null });
      })
      .catch((err) => setLoadError(err.message));
  }, [id]);

  // Load: a saved resume by id, a document handed over from the scanner, or the local draft.
  useEffect(() => {
    if (id) {
      if (authStatus === "checking") return;
      if (authStatus !== "authenticated") {
        navigate("/login", { replace: true, state: { from: location.pathname } });
        return;
      }
      loadSaved();
      return;
    }
    const handoff = location.state?.importDocument;
    if (handoff) {
      setDoc(withKeys(handoff));
      setJd(location.state.jobDescription || "");
      setTitle(location.state.title || "Imported resume");
      setImported(true);
      navigate(location.pathname, { replace: true, state: null });
      return;
    }
    const draft = loadDraft();
    setDoc(draft?.document || emptyDocument());
    setJd(draft?.jobDescription || "");
    setTitle(draft?.title || "My resume");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per resume / auth state
  }, [id, authStatus]);

  // Anonymous drafts live in the browser until the user saves them to an account.
  useEffect(() => {
    if (!id && doc) saveDraft({ document: doc, jobDescription: jd, title });
  }, [id, doc, jd, title]);

  const dirty = useMemo(
    () => Boolean(id && saved && doc && snapshotOf(title, doc, jd) !== saved.snapshot),
    [id, saved, doc, title, jd]
  );

  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const { result: score, error: scoreError, pending } = useLiveScore(doc, jd);

  const save = useCallback(async () => {
    if (!doc) return;
    if (!id) {
      if (authStatus !== "authenticated") {
        navigate("/login", { state: { from: "/builder", reason: "save" } });
        return;
      }
      setSaveState({ status: "saving", message: null });
      try {
        const created = await resumes.create(title.trim() || "Untitled resume", doc, jd);
        clearDraft();
        navigate(`/builder/${created.id}`, { replace: true });
      } catch (err) {
        setSaveState({ status: "error", message: err.message });
      }
      return;
    }
    setSaveState({ status: "saving", message: null });
    try {
      const updated = await resumes.update(id, {
        title: title.trim() || "Untitled resume",
        document: doc,
        targetJobDescription: jd,
        version: saved.version,
      });
      setSaved({ version: updated.version, snapshot: snapshotOf(title, doc, jd) });
      setSaveState({ status: "saved", message: null });
    } catch (err) {
      setSaveState({ status: err.status === 409 ? "conflict" : "error", message: err.message });
    }
  }, [doc, id, authStatus, navigate, title, jd, saved]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  async function handleExport(format) {
    setExporting(format);
    try {
      const name = doc.basics.name ? `${doc.basics.name} Resume` : title || "Resume";
      const blob = await exportDocument(doc, format, name);
      downloadBlob(blob, `${name.replace(/[^\w.-]+/g, "_")}.${format}`);
    } catch (err) {
      setSaveState({ status: "error", message: err.message });
    } finally {
      setExporting(null);
    }
  }

  function resetDraft() {
    if (!window.confirm("Clear this draft and start from a blank resume?")) return;
    clearDraft();
    setDoc(emptyDocument());
    setJd("");
    setTitle("My resume");
    setImported(false);
  }

  if (loadError) {
    return (
      <div className="hud-panel page-message">
        <p className="error-text">⚠ {loadError}</p>
        <Link to="/resumes">Back to my resumes</Link>
      </div>
    );
  }
  if (!doc) return <div className="hud-panel page-message">Loading resume…</div>;

  const update = (key) => (value) => setDoc((d) => ({ ...d, [key]: value }));
  const flagged = score?.flagged_lines;
  const statusText = {
    saving: "Saving…",
    saved: "All changes saved",
    conflict: saveState.message,
    error: saveState.message,
  }[saveState.status] || (id ? (dirty ? "Unsaved changes" : "All changes saved") : "Draft saved in this browser");

  return (
    <div className="builder">
      <div className="builder-toolbar hud-panel">
        <input className="builder-title" type="text" aria-label="Resume name" value={title}
          onChange={(e) => setTitle(e.target.value)} maxLength={200} />
        <select aria-label="Template" value={doc.template} onChange={(e) => update("template")(e.target.value)}>
          <option value="classic">Classic template</option>
          <option value="compact">Compact template</option>
        </select>
        <span className={`save-status save-status--${saveState.status} ${dirty ? "is-dirty" : ""}`} role="status">
          {statusText}
          {saveState.status === "conflict" && (
            <button type="button" className="btn-ghost btn-small" onClick={() => {
              if (window.confirm("Load the latest saved version? Your unsaved edits here will be lost.")) loadSaved();
            }}>Load latest</button>
          )}
        </span>
        <div className="builder-actions">
          {!id && <button type="button" className="btn-ghost btn-small" onClick={resetDraft}>New blank</button>}
          <button type="button" className="btn-small" onClick={save} disabled={saveState.status === "saving" || (id && !dirty)}>
            {id ? "Save" : authStatus === "authenticated" ? "Save to account" : "Sign in to save"}
          </button>
          <button type="button" className="btn-ghost btn-small" onClick={() => handleExport("pdf")} disabled={!!exporting}>
            {exporting === "pdf" ? "Exporting…" : "↓ PDF"}
          </button>
          <button type="button" className="btn-ghost btn-small" onClick={() => handleExport("docx")} disabled={!!exporting}>
            {exporting === "docx" ? "Exporting…" : "↓ DOCX"}
          </button>
        </div>
      </div>

      <div className="builder-layout">
        <div className="builder-editor">
          {imported && (
            <div className="notice">
              Imported from your file. Automatic parsing isn&apos;t perfect — check each section before exporting.
              <button type="button" className="icon-btn" onClick={() => setImported(false)} aria-label="Dismiss">✕</button>
            </div>
          )}
          <BasicsEditor basics={doc.basics} onChange={update("basics")} />
          <ExperienceEditor items={doc.experience} onChange={update("experience")} flaggedLines={flagged} />
          <SkillsEditor groups={doc.skills} onChange={update("skills")} missingKeywords={jd.trim() ? score?.keywords.missing : null} />
          <EducationEditor items={doc.education} onChange={update("education")} />
          <ProjectsEditor items={doc.projects} onChange={update("projects")} flaggedLines={flagged} />
          <CertificationsEditor items={doc.certifications} onChange={update("certifications")} />
        </div>

        <aside className="builder-side">
          <div className="tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === "score"} className={tab === "score" ? "is-active" : ""} onClick={() => setTab("score")}>
              Score {score && <span className="tab-badge">{Math.round(score.ats_score)}</span>}
            </button>
            <button type="button" role="tab" aria-selected={tab === "preview"} className={tab === "preview" ? "is-active" : ""} onClick={() => setTab("preview")}>
              Preview
            </button>
          </div>
          <div className="builder-side__body hud-panel">
            {tab === "score" ? (
              <ScorePanel score={score} pending={pending} error={scoreError} jobDescription={jd} onJobDescriptionChange={setJd} />
            ) : (
              <ResumePreview document={doc} />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
