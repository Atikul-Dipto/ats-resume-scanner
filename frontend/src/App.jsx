import { useEffect, useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import LoadingScan from "./components/LoadingScan.jsx";
import PaperField from "./components/PaperField.jsx";
import ThemeSwitcher from "./components/ThemeSwitcher.jsx";
import { analyzeResume } from "./api/client.js";
import { applyTheme, getStoredThemeId } from "./theme.js";

export default function App() {
  const [themeId, setThemeId] = useState(getStoredThemeId);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  async function handleSubmit(file, jobDescription) {
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeResume(file, jobDescription);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <PaperField />
      <div className="scan-grid" aria-hidden="true" />
      <ThemeSwitcher activeId={themeId} onChange={setThemeId} />

      <header className="app-header">
        <p className="app-eyebrow">// APPLICANT TRACKING SYSTEM DIAGNOSTICS</p>
        <h1>ATS Resume Scanner</h1>
        <p>Run a compatibility scan, pinpoint exactly what's holding your resume back, then find matching roles.</p>
      </header>

      {loading && <LoadingScan />}

      {!loading && !result && (
        <>
          <UploadForm onSubmit={handleSubmit} loading={loading} />
          {error && <p className="error-text">⚠ {error}</p>}
        </>
      )}

      {!loading && result && <ResultsPanel result={result} onReset={() => setResult(null)} />}

      <footer className="app-footer">
        <span>Built with React + FastAPI · Job data via Remotive, Arbeitnow &amp; The Muse</span>
      </footer>
    </div>
  );
}
