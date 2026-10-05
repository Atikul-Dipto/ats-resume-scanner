import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { jobs as jobsApi } from "../api/client.js";
import { DISCIPLINES, WORKPLACES, loadProfile, saveProfile } from "../jobs/format.js";
import JobCard from "../jobs/JobCard.jsx";
import ProfilePicker from "../jobs/ProfilePicker.jsx";
import { useAssistantPage } from "../assistant/AssistantContext.jsx";

const PAGE_SIZE = 20;

export default function JobsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(() => {
    const handoff = location.state?.profile; // from the scan results page
    if (handoff) saveProfile(handoff);
    return handoff || loadProfile();
  });
  useAssistantPage({ page: "jobs", document: profile?.document });
  const [filters, setFilters] = useState({ discipline: "", workplace: "", source: "", q: "" });
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [catalog, setCatalog] = useState(null);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Auto-select the detected discipline once per chosen resume, not on every refetch.
  const appliedFor = useRef(null);

  useEffect(() => {
    if (location.state?.profile) navigate(location.pathname, { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- consume the hand-off once
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      setFilters((f) => (f.q === searchInput.trim() ? f : { ...f, q: searchInput.trim() }));
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const profileKey = profile ? `${profile.kind}:${profile.label}` : null;

  // Catalog listing: provides facet counts always, and the results when not matching.
  useEffect(() => {
    let cancelled = false;
    jobsApi
      .list({ ...filters, page: profile ? 1 : page, page_size: profile ? 1 : PAGE_SIZE })
      .then((data) => !cancelled && setCatalog(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [filters, page, profile]);

  // Ranked results for the chosen resume.
  useEffect(() => {
    if (!profile) {
      setMatch(null);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    jobsApi
      .match(profile.document, {
        discipline: filters.discipline || null,
        workplace: filters.workplace || null,
        source: filters.source || null,
        q: filters.q || null,
        limit: 50,
      }, controller.signal)
      .then((data) => {
        setMatch(data);
        const detected = data.profile.detected_discipline;
        if (appliedFor.current !== profileKey) {
          appliedFor.current = profileKey;
          if (detected && !filters.discipline) setFilters((f) => ({ ...f, discipline: detected }));
        }
      })
      .catch((err) => err.name !== "AbortError" && setError(err.message))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [profile, profileKey, filters]);

  useEffect(() => {
    if (!profile && catalog) setLoading(false);
  }, [profile, catalog]);

  function changeProfile(next) {
    saveProfile(next);
    appliedFor.current = null;
    setProfile(next);
    setFilters((f) => ({ ...f, discipline: "" }));
  }

  const setFilter = (key) => (value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  const facets = catalog?.facets || {};
  const allCount = Object.values(facets).reduce((a, b) => a + b, 0);
  const items = profile ? match?.results : catalog?.items;
  const total = profile ? match?.total_considered : catalog?.total;
  const pages = !profile && catalog ? Math.max(1, Math.ceil(catalog.total / PAGE_SIZE)) : 1;
  const detected = match?.profile.detected_discipline;

  return (
    <div className="jobs-page">
      <header className="app-header">
        <p className="app-eyebrow">Engineering &amp; data jobs</p>
        <h1>Find jobs that fit your resume</h1>
        <p>Data, software, civil, electrical, mechanical and textile roles — ranked by how well your resume matches each one.</p>
      </header>

      <ProfilePicker profile={profile} onChange={changeProfile} />

      {match?.profile && (
        <p className="profile-summary">
          Read as <strong>{match.profile.title || "untitled role"}</strong>
          {match.profile.years_experience != null && <> · ~{match.profile.years_experience} yrs experience</>}
          {detected && <> · {DISCIPLINES[detected]}</>} · {match.profile.skills.length} skills recognised
        </p>
      )}

      <div className="jobs-filters hud-panel">
        <div className="discipline-chips" role="group" aria-label="Discipline">
          <button type="button" className={`filter-chip ${!filters.discipline ? "is-active" : ""}`} onClick={() => setFilter("discipline")("")}>
            All <span>{allCount}</span>
          </button>
          {Object.entries(DISCIPLINES).map(([key, label]) => (
            <button type="button" key={key} className={`filter-chip ${filters.discipline === key ? "is-active" : ""}`}
              onClick={() => setFilter("discipline")(key)}>
              {label} <span>{facets[key] || 0}</span>
              {detected === key && <em title="Detected from your resume"> ★</em>}
            </button>
          ))}
        </div>
        <div className="jobs-filters__row">
          <input type="text" aria-label="Search jobs" placeholder="Search title, company or location…" value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)} />
          <select aria-label="Workplace" value={filters.workplace} onChange={(e) => setFilter("workplace")(e.target.value)}>
            <option value="">Any workplace</option>
            {Object.entries(WORKPLACES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select aria-label="Source" value={filters.source} onChange={(e) => setFilter("source")(e.target.value)}>
            <option value="">All listings</option>
            <option value="local">Posted here (Bangladesh)</option>
            <option value="remote">Remote (international)</option>
          </select>
        </div>
      </div>

      {error && <p className="error-text">⚠ {error}</p>}
      {loading && !items && <p className="no-issues">Loading jobs…</p>}
      {items && (
        <p className="jobs-count" aria-live="polite">
          {profile ? `${total} job${total === 1 ? "" : "s"} ranked by match` : `${total} open job${total === 1 ? "" : "s"}`}
          {loading && " · updating…"}
        </p>
      )}
      {items?.length === 0 && (
        <div className="hud-panel page-message">
          No open jobs match these filters yet. Try another discipline or clear the search.
        </div>
      )}

      {items?.length > 0 && (
        <ul className="job-list">
          {profile
            ? items.map((m) => <JobCard key={m.job.id} job={m.job} match={m} />)
            : items.map((job) => <JobCard key={job.id} job={job} />)}
        </ul>
      )}

      {!profile && pages > 1 && (
        <div className="pagination">
          <button type="button" className="btn-ghost btn-small" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Prev</button>
          <span>Page {page} of {pages}</span>
          <button type="button" className="btn-ghost btn-small" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
