import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import NavBar from "./components/NavBar.jsx";
import PaperField from "./components/PaperField.jsx";
import AdminJobsPage from "./pages/AdminJobsPage.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import BuilderPage from "./pages/BuilderPage.jsx";
import JobDetailPage from "./pages/JobDetailPage.jsx";
import JobsPage from "./pages/JobsPage.jsx";
import ResumesPage from "./pages/ResumesPage.jsx";
import ScanPage from "./pages/ScanPage.jsx";
import { applyTheme, getStoredThemeId } from "./theme.js";

export default function App() {
  const [themeId, setThemeId] = useState(getStoredThemeId);
  const { pathname } = useLocation();
  const wide = pathname.startsWith("/builder");

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  return (
    <>
      <PaperField />
      <div className="scan-grid" aria-hidden="true" />
      <NavBar themeId={themeId} onThemeChange={setThemeId} />

      <main className={`app ${wide ? "app--wide" : ""}`}>
        <Routes>
          <Route path="/" element={<ScanPage />} />
          <Route path="/builder" element={<BuilderPage />} />
          <Route path="/builder/:id" element={<BuilderPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/admin/jobs" element={<AdminJobsPage />} />
          <Route path="/login" element={<AuthPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        <footer className="app-footer">
          <span>Built with React + FastAPI · Job data via Remotive, Arbeitnow &amp; The Muse · Uploaded files are never stored</span>
        </footer>
      </main>
    </>
  );
}
