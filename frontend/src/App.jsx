import { useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import { analyzeResume } from "./api/client.js";

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
      <header className="app-header">
        <h1>ATS Resume Scanner</h1>
        <p>Check how ATS-friendly your resume is, then find matching jobs in seconds.</p>
      </header>

      {!result && (
        <>
          <UploadForm onSubmit={handleSubmit} loading={loading} />
          {error && <p className="error-text">{error}</p>}
        </>
      )}

      {result && <ResultsPanel result={result} onReset={() => setResult(null)} />}

      <footer className="app-footer">
        <span>Built with React + FastAPI · Job data via Remotive, Arbeitnow &amp; The Muse</span>
      </footer>
    </div>
  );
}
