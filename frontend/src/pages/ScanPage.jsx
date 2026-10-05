import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeResume } from "../api/client.js";
import { isBlank, loadDraft } from "../builder/model.js";
import LoadingScan from "../components/LoadingScan.jsx";
import ResultsPanel from "../components/ResultsPanel.jsx";
import UploadForm from "../components/UploadForm.jsx";

export default function ScanPage() {
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(file, jd) {
    setLoading(true);
    setError(null);
    try {
      setResult(await analyzeResume(file, jd));
      setJobDescription(jd);
      setFileName(file.name.replace(/\.(pdf|docx)$/i, ""));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function openInBuilder() {
    const existing = loadDraft();
    if (existing && !isBlank(existing.document) &&
        !window.confirm("Replace the resume draft currently in the builder with this one?")) {
      return;
    }
    navigate("/builder", {
      state: { importDocument: result.draft_document, jobDescription, title: fileName || "Imported resume" },
    });
  }

  function findJobs() {
    navigate("/jobs", {
      state: { profile: { kind: "scan", label: fileName ? `${fileName} (scanned)` : "Scanned resume", document: result.draft_document } },
    });
  }

  return (
    <>
      <header className="app-header">
        <p className="app-eyebrow">// APPLICANT TRACKING SYSTEM DIAGNOSTICS</p>
        <h1>ATS Resume Scanner</h1>
        <p>Run a compatibility scan, pinpoint exactly what&apos;s holding your resume back, then fix it in the builder.</p>
      </header>

      {loading && <LoadingScan />}

      {!loading && !result && (
        <>
          <UploadForm onSubmit={handleSubmit} loading={loading} />
          {error && <p className="error-text">⚠ {error}</p>}
        </>
      )}

      {!loading && result && (
        <ResultsPanel result={result} onReset={() => setResult(null)} onOpenInBuilder={openInBuilder} onFindJobs={findJobs} />
      )}
    </>
  );
}
