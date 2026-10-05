import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { jobs as jobsApi } from "../api/client.js";
import { isBlank, loadDraft } from "../builder/model.js";
import {
  DISCIPLINES,
  EMPLOYMENT_TYPES,
  WORKPLACES,
  formatDeadline,
  formatExperience,
  formatSalary,
  loadProfile,
  matchLabel,
  matchTier,
  safeHref,
  sourceLabel,
} from "../jobs/format.js";

export default function JobDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const match = location.state?.match || null;
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    jobsApi.get(id).then(setJob).catch((err) => setError(err.message));
  }, [id]);

  function tailor() {
    const jobDescription = `${job.title} — ${job.company}\n\n${job.description}`;
    const tailorJob = { title: job.title, company: job.company, description: jobDescription };
    const profile = loadProfile();
    if (profile?.kind === "saved") {
      navigate(`/builder/${profile.resumeId}`, { state: { tailorJob } });
      return;
    }
    if (profile?.kind === "scan") {
      // The scanned resume isn't in the builder yet: bring it along.
      const draft = loadDraft();
      if (draft && !isBlank(draft.document) &&
          !window.confirm("Replace the resume draft currently in the builder with the one you're matching?")) {
        return;
      }
      navigate("/builder", { state: { importDocument: profile.document, jobDescription, title: profile.label, tailorJob } });
      return;
    }
    navigate("/builder", { state: { tailorJob } });
  }

  if (error) {
    return (
      <div className="hud-panel page-message">
        <p className="error-text">⚠ {error}</p>
        <Link to="/jobs">Back to jobs</Link>
      </div>
    );
  }
  if (!job) return <div className="hud-panel page-message">Loading job…</div>;

  const apply = safeHref(job.apply_url);
  const facts = [
    ["Discipline", DISCIPLINES[job.discipline]],
    ["Workplace", WORKPLACES[job.workplace] || job.workplace],
    ["Type", EMPLOYMENT_TYPES[job.employment_type] || job.employment_type],
    ["Experience", formatExperience(job)],
    ["Salary", formatSalary(job)],
    ["Deadline", formatDeadline(job.deadline)],
    ["Source", sourceLabel(job.source)],
  ].filter(([, v]) => v);

  return (
    <div className="job-detail">
      <Link to="/jobs" className="back-link">← All jobs</Link>
      <header className="job-detail__head hud-panel">
        <div>
          <h1>{job.title}</h1>
          <p className="job-detail__company">{job.company}{job.location && ` · ${job.location}`}</p>
          <dl className="job-facts">
            {facts.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </div>
        <div className="job-detail__actions">
          {apply && (
            <a className="button-link" href={apply} target="_blank" rel="noopener noreferrer">
              Apply {job.source === "local" ? "now" : `on ${sourceLabel(job.source).replace("via ", "")}`} ↗
            </a>
          )}
          <button type="button" className="btn-ghost" onClick={tailor}>Tailor my resume for this job</button>
        </div>
      </header>

      {match && (
        <section className="hud-panel job-detail__match">
          <div className={`match-badge match-badge--large tier-${matchTier(match.match_score)}`}>
            <strong>{Math.round(match.match_score)}%</strong>
            <span>{matchLabel(match.match_score)}</span>
          </div>
          <div className="job-detail__match-body">
            {match.matched_skills.length > 0 && (
              <>
                <h3>You have</h3>
                <div className="chip-list">{match.matched_skills.map((s) => <span key={s} className="chip chip-matched">✓ {s}</span>)}</div>
              </>
            )}
            {match.missing_skills.length > 0 && (
              <>
                <h3>Not on your resume</h3>
                <div className="chip-list">{match.missing_skills.map((s) => <span key={s} className="chip chip-missing">{s}</span>)}</div>
                <p className="field-hint">If you genuinely have these, adding them (with evidence in a bullet) raises your match.</p>
              </>
            )}
            {match.experience_note && <p className="match-note">⚠ {match.experience_note}</p>}
          </div>
        </section>
      )}

      <section className="hud-panel job-detail__body">
        <h2>About the role</h2>
        <div className="job-description">{job.description}</div>
        {job.skills.length > 0 && (
          <>
            <h3>Skills mentioned</h3>
            <div className="chip-list">{job.skills.map((s) => <span key={s} className="chip">{s}</span>)}</div>
          </>
        )}
      </section>
    </div>
  );
}
