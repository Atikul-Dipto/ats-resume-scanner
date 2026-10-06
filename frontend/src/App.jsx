import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import NavBar, { Logo } from "./components/NavBar.jsx";
import PaperField from "./components/PaperField.jsx";
import AssistantDock from "./assistant/AssistantDock.jsx";
import { AssistantProvider } from "./assistant/AssistantContext.jsx";
import AdminJobsPage from "./pages/AdminJobsPage.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import BuilderPage from "./pages/BuilderPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import JobDetailPage from "./pages/JobDetailPage.jsx";
import JobsPage from "./pages/JobsPage.jsx";
import MarketPage from "./pages/MarketPage.jsx";
import ResumesPage from "./pages/ResumesPage.jsx";
import ScanPage from "./pages/ScanPage.jsx";
import { applyMode, getInitialMode } from "./theme.js";

export default function App() {
  const [mode, setMode] = useState(getInitialMode);
  const { pathname } = useLocation();
  const layout = pathname === "/" ? "app--full" : pathname.startsWith("/builder") ? "app--wide" : "";

  useEffect(() => {
    applyMode(mode);
  }, [mode]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);

  return (
    <AssistantProvider>
      <NavBar mode={mode} onModeChange={setMode} />
      {pathname === "/scan" && <PaperField />}

      <main className={`app ${layout}`}>
        {/* Keyed by path so every navigation plays the page-enter motion. */}
        <div key={pathname} className="page-enter">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/builder" element={<BuilderPage />} />
            <Route path="/builder/:id" element={<BuilderPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/market" element={<MarketPage />} />
            <Route path="/resumes" element={<ResumesPage />} />
            <Route path="/admin/jobs" element={<AdminJobsPage />} />
            <Route path="/login" element={<AuthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>

      <footer className="app-footer">
        <div className="app-footer__inner">
          <Link to="/" className="navbar__brand"><Logo /></Link>
          <span>The career center for job seekers · Uploaded files are never stored</span>
          <span>
            <Link to="/scan">Scan</Link> · <Link to="/builder">Builder</Link> · <Link to="/jobs">Jobs</Link> · <Link to="/market">Work Signal</Link>
          </span>
        </div>
      </footer>

      <AssistantDock />
    </AssistantProvider>
  );
}
