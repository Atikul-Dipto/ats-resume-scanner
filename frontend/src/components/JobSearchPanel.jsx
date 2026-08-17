import { useState } from "react";
import { searchJobs } from "../api/client.js";

export default function JobSearchPanel({ profile }) {
  const [query, setQuery] = useState(profile.current_title || profile.skills.slice(0, 2).join(" ") || "");
  const [location, setLocation] = useState("");
  const [jobs, setJobs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await searchJobs(query.trim(), profile.skills, location.trim());
      setJobs(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="job-search-panel">
      <form onSubmit={handleSearch} className="job-search-form">
        <input
          type="text"
          placeholder="Role or keywords"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          type="text"
          placeholder="Location (optional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Find matching jobs"}
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}

      {jobs && jobs.length === 0 && <p className="no-issues">No matching jobs found — try different keywords.</p>}

      {jobs && jobs.length > 0 && (
        <ul className="job-results">
          {jobs.map((job, i) => (
            <li key={i} className="job-card">
              <div className="job-card-main">
                <a href={job.url} target="_blank" rel="noreferrer">
                  {job.title}
                </a>
                <span className="job-company">
                  {job.company} {job.location ? `· ${job.location}` : ""}
                </span>
              </div>
              <div className="job-card-meta">
                <span className="job-source">{job.source}</span>
                <span className="job-relevance">{Math.round(job.relevance_score)}% match</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
