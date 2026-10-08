import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { exportDocument, resumes } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import DesignPanel from "../builder/DesignPanel.jsx";
import ResumePreview from "../builder/ResumePreview.jsx";
import ScorePanel from "../builder/ScorePanel.jsx";
import {
  BasicsEditor,
  CertificationsEditor,
  EducationEditor,
  ExperienceEditor,
  ProjectsEditor,
  SectionCard,
  SkillsEditor,
} from "../builder/SectionEditors.jsx";
import { clearDraft, downloadBlob, emptyDocument, loadDraft, saveDraft, withKeys } from "../builder/model.js";
import { TEMPLATE_IDS, TEMPLATES, withTemplate } from "../builder/templates.js";
import useLiveScore from "../builder/useLiveScore.js";
import { useAssistant, useAssistantPage } from "../assistant/AssistantContext.jsx";

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
  const [fullscreen, setFullscreen] = useState(false);
  // "Tailor my resume for this job" from the job board: load that posting as
  // the target job once the resume itself has loaded.
  const [tailorJob, setTailorJob] = useState(() => location.state?.tailorJob || null);
  const tailorApplied = useRef(false);

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

  useEffect(() => {
    if (!doc || !tailorJob || tailorApplied.current) return;
    tailorApplied.current = true;
    setJd(tailorJob.description);
    setTab("score");
    if (location.state) navigate(location.pathname, { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- apply once, after the resume loads
  }, [doc, tailorJob]);

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
  const ai = useAssistant();
  useAssistantPage({ page: "builder", document: doc, jobDescription: jd, apply: setDoc });

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

  // Full-screen preview: Esc closes it, and the page behind doesn't scroll.
  useEffect(() => {
    if (!fullscreen) return undefined;
    const onKey = (e) => e.key === "Escape" && setFullscreen(false);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [fullscreen]);

  const exportName = () => (doc.basics.name ? `${doc.basics.name} Resume` : title || "Resume");

  async function handleExport(format) {
    setExporting(format);
    try {
      const name = exportName();
      const blob = await exportDocument(doc, format, name);
      downloadBlob(blob, `${name.replace(/[^\w.-]+/g, "_")}.${format}`);
    } catch (err) {
      setSaveState({ status: "error", message: err.message });
    } finally {
      setExporting(null);
    }
  }

  // Overleaf's "open a snippet" endpoint takes a form POST. The tab is opened
  // first, inside the click, so popup blockers allow it.
  async function openInOverleaf() {
    const overleafTab = window.open("", "prottoy-overleaf");
    setExporting("overleaf");
    try {
      const tex = await (await exportDocument(doc, "tex", exportName())).text();
      const form = document.createElement("form");
      form.method = "POST";
      form.action = "https://www.overleaf.com/docs";
      form.target = "prottoy-overleaf";
      const fields = {
        encoded_snip: encodeURIComponent(tex),
        snip_name: "resume.tex",
        engine: tex.startsWith("% !TEX program = lualatex") ? "lualatex" : "pdflatex",
      };
      for (const [name, value] of Object.entries(fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
      form.remove();
    } catch (err) {
      overleafTab?.close();
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
        <select aria-label="Template" value={doc.template} onChange={(e) => setDoc((d) => withTemplate(d, e.target.value))}>
          {TEMPLATE_IDS.map((t) => (
            <option key={t} value={t}>{TEMPLATES[t].label} template</option>
          ))}
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
          {ai.enabled && (
            <button type="button" className="btn-small ai-open-btn" onClick={() => ai.openAssistant()}>✦ AI assist</button>
          )}
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
          <button type="button" className="btn-ghost btn-small" onClick={() => handleExport("tex")} disabled={!!exporting}
            title="LaTeX source of this template, ready to compile">
            {exporting === "tex" ? "Exporting…" : "↓ LaTeX"}
          </button>
          <button type="button" className="btn-ghost btn-small" onClick={openInOverleaf} disabled={!!exporting}
            title="Open the LaTeX source as a new Overleaf project (sends your resume to overleaf.com)">
            {exporting === "overleaf" ? "Opening…" : "↗ Overleaf"}
          </button>
        </div>
      </div>

      <div className={`builder-layout${tab === "preview" ? " builder-layout--preview" : ""}`}>
        <div className="builder-editor">
          {tailorJob && (
            <div className="notice notice--accent">
              <span>
                Tailoring for <strong>{tailorJob.title}</strong> at {tailorJob.company}. Its description is loaded as the
                target job — the Score panel shows which of its keywords your resume is missing.
              </span>
              <button type="button" className="icon-btn" onClick={() => setTailorJob(null)} aria-label="Dismiss">✕</button>
            </div>
          )}
          {imported && (
            <div className="notice">
              Imported from your file. Automatic parsing isn&apos;t perfect — check each section before exporting.
              <button type="button" className="icon-btn" onClick={() => setImported(false)} aria-label="Dismiss">✕</button>
            </div>
          )}
          <SectionCard title={`Template & design · ${TEMPLATES[doc.template].label}`} icon="◧" defaultOpen={false}
            className="editor-card--design" onToggle={(open) => open && setTab("preview")}>
            <DesignPanel document={doc} onChange={setDoc} />
          </SectionCard>
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
              <ResumePreview document={doc} onExpand={() => setFullscreen(true)} />
            )}
          </div>
        </aside>
      </div>

      {/* Portalled: .builder's entry animation transforms it, which would trap position: fixed. */}
      {fullscreen && createPortal(
        <div className="preview-modal" role="dialog" aria-modal="true" aria-label="Full-screen resume preview">
          <aside className="preview-modal__design">
            <h2>Template &amp; design</h2>
            <DesignPanel document={doc} onChange={setDoc} />
          </aside>
          <div className="preview-modal__stage">
            <ResumePreview document={doc} expanded onExpand={() => setFullscreen(false)} />
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
