import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { jobs as jobsApi } from "../api/client.js";
import { DISCIPLINES, WORKPLACES, safeHref, sourceLabel } from "../jobs/format.js";

const REFRESH_MS = 60_000;

// The newest open jobs, refreshed in place; jobs that appear after the first
// load are marked "New" and slide in.
export default function JobFeed() {
  const [items, setItems] = useState(null);
  const [fresh, setFresh] = useState(() => new Set());
  const seen = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      jobsApi
        .list({ page_size: 6 })
        .then((data) => {
          if (cancelled) return;
          const ids = data.items.map((j) => j.id);
          if (seen.current) setFresh(new Set(ids.filter((id) => !seen.current.has(id))));
          seen.current = new Set([...(seen.current || []), ...ids]);
          setItems(data.items);
        })
        .catch(() => !cancelled && setItems((cur) => cur ?? []));
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (items === null) {
    return <div className="job-feed">{[0, 1, 2].map((i) => <div key={i} className="job-feed__item skeleton" />)}</div>;
  }
  if (items.length === 0) {
    return <p className="no-issues">Fresh jobs appear here as soon as the catalog syncs.</p>;
  }
  return (
    <ul className="job-feed">
      {items.map((job, i) => {
        const apply = safeHref(job.apply_url);
        return (
          <li key={job.id} className={`job-feed__item ${fresh.has(job.id) ? "is-new" : ""}`} style={{ "--i": i }}>
            <div className="job-feed__main">
              <Link to={`/jobs/${job.id}`} className="job-feed__title">{job.title}</Link>
              <span className="job-feed__meta">
                {job.company}{job.location && ` · ${job.location}`}
              </span>
              <span className="job-tags">
                <span className="job-tag job-tag--discipline">{DISCIPLINES[job.discipline]}</span>
                <span className="job-tag">{WORKPLACES[job.workplace] || job.workplace}</span>
                <span className="job-tag">{sourceLabel(job.source)}</span>
                {fresh.has(job.id) && <span className="job-tag job-tag--new">New</span>}
              </span>
            </div>
            {apply && (
              <a className="button-link button-link--small" href={apply} target="_blank" rel="noopener noreferrer">
                Apply ↗
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}
