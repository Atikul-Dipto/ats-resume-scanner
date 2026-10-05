import { Link } from "react-router-dom";
import {
  DISCIPLINES,
  EMPLOYMENT_TYPES,
  WORKPLACES,
  formatDeadline,
  formatExperience,
  formatSalary,
  matchLabel,
  matchTier,
  safeHref,
  sourceLabel,
} from "./format.js";

export default function JobCard({ job, match }) {
  const salary = formatSalary(job);
  const experience = formatExperience(job);
  const deadline = formatDeadline(job.deadline);
  const apply = safeHref(job.apply_url);

  return (
    <li className="job-listing hud-panel">
      <Link to={`/jobs/${job.id}`} state={{ match }} className="job-listing__link">
        <div className="job-listing__head">
          <div className="job-listing__title">
            <h3>{job.title}</h3>
            <p>
              {job.company}
              {job.location && ` · ${job.location}`}
            </p>
          </div>
          {match && (
            <div className={`match-badge tier-${matchTier(match.match_score)}`} title={matchLabel(match.match_score)}>
              <strong>{Math.round(match.match_score)}%</strong>
              <span>{matchLabel(match.match_score)}</span>
            </div>
          )}
        </div>

        <div className="job-tags">
          <span className="job-tag job-tag--discipline">{DISCIPLINES[job.discipline]}</span>
          <span className="job-tag">{WORKPLACES[job.workplace] || job.workplace}</span>
          <span className="job-tag">{EMPLOYMENT_TYPES[job.employment_type] || job.employment_type}</span>
          {experience && <span className="job-tag">{experience}</span>}
          {salary && <span className="job-tag job-tag--salary">{salary}</span>}
          <span className={`job-tag ${job.source === "local" ? "job-tag--local" : ""}`}>{sourceLabel(job.source)}</span>
          {deadline && <span className="job-tag job-tag--deadline">{deadline}</span>}
        </div>

        {match ? (
          <div className="match-detail">
            {match.matched_skills.length > 0 && (
              <div className="chip-list">
                {match.matched_skills.slice(0, 6).map((s) => <span key={s} className="chip chip-matched">✓ {s}</span>)}
              </div>
            )}
            {match.missing_skills.length > 0 && (
              <div className="chip-list">
                {match.missing_skills.slice(0, 6).map((s) => <span key={s} className="chip chip-missing">{s}</span>)}
              </div>
            )}
            {match.experience_note && <p className="match-note">⚠ {match.experience_note}</p>}
          </div>
        ) : (
          job.snippet && <p className="job-listing__snippet">{job.snippet}</p>
        )}
      </Link>
      {apply && (
        <a className="job-listing__apply button-link button-link--small" href={apply} target="_blank" rel="noopener noreferrer"
          aria-label={`Apply for ${job.title} at ${job.company} (opens the original posting)`}>
          Apply ↗
        </a>
      )}
    </li>
  );
}
