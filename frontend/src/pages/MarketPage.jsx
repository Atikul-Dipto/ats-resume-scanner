import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { market as marketApi, marketIndicators } from "../api/client.js";
import { useAssistantPage } from "../assistant/AssistantContext.jsx";
import useCountUp from "../hooks/useCountUp.js";
import { DISCIPLINES, WORKPLACES, safeHref } from "../jobs/format.js";

const REFRESH_MS = 5 * 60 * 1000;
const bdt = (n) => `৳${Math.round(n).toLocaleString("en-IN")}`;
const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

function jobsLink(params) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
  const s = qs.toString();
  return `/jobs${s ? `?${s}` : ""}`;
}

function since(iso) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  return minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`;
}

function Tile({ label, value, format = (v) => v.toLocaleString(), note, to }) {
  const shown = Math.round(useCountUp(typeof value === "number" ? value : 0));
  const body = (
    <>
      <span className="ws-tile__label">{label}</span>
      <strong className="ws-tile__value">{typeof value === "number" ? format(shown) : value}</strong>
      {note && <small className="ws-tile__note">{note}</small>}
    </>
  );
  return to ? <Link to={to} className="ws-tile ws-tile--link">{body}</Link> : <div className="ws-tile">{body}</div>;
}

/** Horizontal bars, one hue; every row links to the postings it counts. */
function BarList({ rows, max, unit = "jobs", format = (v) => v.toLocaleString() }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="ws-bars">
      {rows.map((row, i) => {
        const inner = (
          <>
            <span className="ws-bar__name">{row.label}</span>
            <span className="ws-bar__track" aria-hidden="true">
              <span className="ws-bar__fill" style={{ "--w": `${(row.value / top) * 100}%`, "--i": i }} />
            </span>
            <span className="ws-bar__value">{format(row.value)}</span>
            {row.extra}
            <span className="ws-tip" role="tooltip">{row.tip || `${format(row.value)} ${unit}`}</span>
          </>
        );
        return (
          <li key={row.key}>
            {row.to ? (
              <Link to={row.to} className="ws-bar" aria-label={row.aria}>{inner}</Link>
            ) : row.onClick ? (
              <button type="button" className="ws-bar" onClick={row.onClick} aria-label={row.aria}>{inner}</button>
            ) : (
              <div className="ws-bar">{inner}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Trend({ recent, previous }) {
  const delta = recent - previous;
  if (!recent && !previous) return <span className="ws-trend">–</span>;
  if (delta === 0) return <span className="ws-trend">= steady</span>;
  return (
    <span className={`ws-trend ${delta > 0 ? "is-up" : "is-down"}`}>
      {delta > 0 ? "▲" : "▼"} {Math.abs(delta)}
    </span>
  );
}

function WeeklyColumns({ weeks }) {
  const max = Math.max(1, ...weeks.map((w) => w.count));
  const fmt = (d) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return (
    <div className="ws-columns" role="img" aria-label={`New jobs per week: ${weeks.map((w) => `${fmt(w.week_start)} ${w.count}`).join(", ")}`}>
      {weeks.map((w, i) => (
        <div key={w.week_start} className="ws-col">
          <span className="ws-col__value">{i === weeks.length - 1 || w.count === max ? w.count : ""}</span>
          <span className="ws-col__plot">
            <span className="ws-col__bar" style={{ "--h": `${(w.count / max) * 100}%`, "--i": i }} />
          </span>
          <span className="ws-col__label">{i === weeks.length - 1 ? "This wk" : fmt(w.week_start)}</span>
          <span className="ws-tip" role="tooltip">Week of {fmt(w.week_start)}: {w.count} new job{w.count === 1 ? "" : "s"}</span>
        </div>
      ))}
    </div>
  );
}

const SECTOR_IDS = ["SL.AGR.EMPL.ZS", "SL.IND.EMPL.ZS", "SL.SRV.EMPL.ZS"];

function OfficialStats({ data }) {
  const byId = Object.fromEntries(data.indicators.map((i) => [i.id, i]));
  const headline = data.indicators.filter((i) => !SECTOR_IDS.includes(i.id));
  const sectors = SECTOR_IDS.map((id) => byId[id]).filter(Boolean);
  return (
    <section className="ws-panel ws-official" aria-labelledby="ws-official-title">
      <div className="ws-panel__head">
        <div>
          <p className="ws-eyebrow">Official statistics · Bangladesh</p>
          <h2 id="ws-official-title">The wider labour market</h2>
        </div>
        <span className="ws-panel__aside">
          <a href={data.source.url} target="_blank" rel="noopener noreferrer">{data.source.name}</a> · {data.source.license}
        </span>
      </div>
      <div className="ws-official__grid">
        <div className="ws-official__tiles">
          {headline.map((i) => {
            const delta = i.previous ? Math.round((i.value - i.previous.value) * 10) / 10 : null;
            return (
              <div key={i.id} className="ws-stat">
                <span className="ws-stat__label">{i.label}</span>
                <strong className="ws-stat__value">{i.value}%</strong>
                <small className="ws-stat__note">
                  {i.year}
                  {delta !== null && (
                    <> · {delta === 0 ? "no change" : `${delta > 0 ? "▲" : "▼"} ${Math.abs(delta)} pts`} vs {i.previous.year}</>
                  )}
                </small>
              </div>
            );
          })}
        </div>
        {sectors.length > 0 && (
          <div>
            <p className="ws-official__sub">Where people work ({sectors[0].year}, % of employment)</p>
            <BarList
              unit="% of employment"
              max={100}
              format={(v) => `${v}%`}
              rows={sectors.map((s) => ({
                key: s.id, label: s.label.replace("Employment in ", ""), value: s.value,
                tip: `${s.value}% of employed people work in ${s.label.replace("Employment in ", "").toLowerCase()} (${s.year})`,
              }))}
            />
          </div>
        )}
      </div>
      <p className="ws-note">Annual figures, modeled by the ILO and published by the World Bank, so the latest year lags by a year or two.</p>
    </section>
  );
}

function Panel({ eyebrow, title, aside, children, className = "" }) {
  return (
    <section className={`ws-panel ${className}`}>
      <div className="ws-panel__head">
        <div>
          <p className="ws-eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        {aside && <span className="ws-panel__aside">{aside}</span>}
      </div>
      {children}
    </section>
  );
}

export default function MarketPage() {
  useAssistantPage({ page: "market" });
  const [filters, setFilters] = useState({ discipline: "", workplace: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [official, setOfficial] = useState(null);

  useEffect(() => {
    marketIndicators().then(setOfficial).catch(() => setOfficial(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      setLoading(true);
      marketApi(filters)
        .then((d) => {
          if (cancelled) return;
          setData(d);
          setError(null);
        })
        .catch((err) => !cancelled && setError(err.message))
        .finally(() => !cancelled && setLoading(false));
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [filters]);

  const set = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const t = data?.totals;
  const scope = { discipline: filters.discipline, workplace: filters.workplace };
  const scopeLabel = [DISCIPLINES[filters.discipline], WORKPLACES[filters.workplace]?.toLowerCase()].filter(Boolean).join(", ");

  return (
    <div className="ws">
      <header className="ws-hero">
        <div>
          <p className="ws-eyebrow">Work Signal · job-market intelligence</p>
          <h1>See where the <span className="gradient-text">work is moving.</span></h1>
          <p className="ws-hero__lead">
            Live signals from every open engineering and data job on Prottoy. Every skill, company and number links
            to the postings behind it.
          </p>
        </div>
        <div className="ws-live" aria-live="polite">
          <span className={`ws-live__dot ${error ? "is-off" : ""}`} />
          {error ? "Offline" : data ? `Updated ${since(data.generated_at)}` : "Connecting…"}
        </div>
      </header>

      <div className="ws-filters">
        <div className="discipline-chips" role="group" aria-label="Discipline">
          <button type="button" className={`filter-chip ${!filters.discipline ? "is-active" : ""}`} onClick={() => set("discipline", "")}>All fields</button>
          {Object.entries(DISCIPLINES).map(([key, label]) => (
            <button type="button" key={key} className={`filter-chip ${filters.discipline === key ? "is-active" : ""}`}
              onClick={() => set("discipline", key)}>{label}</button>
          ))}
        </div>
        <select aria-label="Work mode" value={filters.workplace} onChange={(e) => set("workplace", e.target.value)}>
          <option value="">Any work mode</option>
          {Object.entries(WORKPLACES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {error && !data && <p className="error-text">⚠ {error}</p>}
      {!data && !error && <div className="ws-skeleton" aria-label="Loading market signals" />}

      {data && t.open_jobs === 0 && (
        <div className="hud-panel page-message">
          No open jobs {scopeLabel ? `in ${scopeLabel} ` : ""}right now, so there&apos;s no signal yet. New listings are
          imported every few hours.
        </div>
      )}

      {data && t.open_jobs > 0 && (
        <div className={`ws-body ${loading ? "is-updating" : ""}`}>
          <section className="ws-tiles" aria-label="Headline numbers">
            <Tile label="Open jobs" value={t.open_jobs} note={scopeLabel || "All fields"} to={jobsLink(scope)} />
            <Tile label="New this week" value={t.new_7d} note="First seen by Prottoy" />
            <Tile label="Companies hiring" value={t.companies} />
            <Tile label="Remote roles" value={pct(t.remote_jobs, t.open_jobs)} format={(v) => `${v}%`}
              note={`${t.remote_jobs.toLocaleString()} open to Bangladesh`} to={jobsLink({ ...scope, workplace: "remote" })} />
            <Tile label="In Bangladesh" value={t.local_jobs} note="On-site or hybrid" />
            <Tile label="Median salary" value={data.salary.median ?? "—"} format={bdt}
              note={data.salary.median ? `per month · ${data.salary.samples} postings list pay` : `${data.salary.samples} postings list pay`} />
          </section>

          <div className="ws-grid">
            <Panel eyebrow="Demand signal" title="Most-demanded skills" aside="vs previous 2 weeks" className="ws-panel--skills">
              <BarList
                unit="open jobs"
                rows={data.skills.map((s) => ({
                  key: s.name,
                  label: s.name,
                  value: s.count,
                  to: jobsLink({ ...scope, skill: s.name }),
                  aria: `${s.name}: ${s.count} open jobs. Show them`,
                  tip: `${s.count} open jobs · ${s.recent} new in the last 14 days (${s.previous} the 14 before) · click to see them`,
                  extra: <Trend recent={s.recent} previous={s.previous} />,
                }))}
              />
            </Panel>

            <Panel eyebrow="Momentum" title="New jobs per week" aside="last 8 weeks">
              <WeeklyColumns weeks={data.weekly_new} />
              <p className="ws-note">Counted when Prottoy first finds a listing.</p>
            </Panel>

            <Panel eyebrow="Hiring map" title="Companies hiring most">
              <BarList
                rows={data.companies.map((c) => ({
                  key: c.name, label: c.name, value: c.count, to: jobsLink({ ...scope, q: c.name }),
                  aria: `${c.name}: ${c.count} open jobs. Show them`,
                }))}
              />
            </Panel>

            <Panel eyebrow="Location" title="Where the jobs are">
              <BarList
                rows={data.locations.map((l) => ({
                  key: l.name, label: l.name, value: l.count,
                  to: l.name === "Remote" ? jobsLink({ ...scope, workplace: "remote" }) : jobsLink({ ...scope, q: l.name }),
                  aria: `${l.name}: ${l.count} open jobs. Show them`,
                }))}
              />
              <div className="ws-modes" aria-label="Work mode split">
                {data.workplaces.map((w) => (
                  <Link key={w.key} to={jobsLink({ ...scope, workplace: w.key })} className="ws-mode">
                    <strong>{pct(w.count, t.open_jobs)}%</strong>
                    <span>{WORKPLACES[w.key]}</span>
                  </Link>
                ))}
              </div>
            </Panel>

            {!filters.discipline && (
              <Panel eyebrow="Field mix" title="Jobs by discipline" aside="click to focus">
                <BarList
                  rows={data.disciplines.map((d) => ({
                    key: d.key, label: DISCIPLINES[d.key], value: d.count,
                    onClick: () => set("discipline", d.key),
                    aria: `${DISCIPLINES[d.key]}: ${d.count} open jobs. Focus the dashboard on it`,
                    tip: `${d.count} open jobs · click to focus Work Signal on ${DISCIPLINES[d.key]}`,
                  }))}
                />
              </Panel>
            )}

            <Panel eyebrow="Pay signal" title="Median monthly salary" aside="BDT, where posted">
              {data.salary.by_discipline.length ? (
                <BarList
                  unit="median per month"
                  format={bdt}
                  rows={data.salary.by_discipline.map((s) => ({
                    key: s.key, label: DISCIPLINES[s.key], value: s.median,
                    tip: `Median ${bdt(s.median)} / month across ${s.samples} postings that list a salary`,
                    to: jobsLink({ ...scope, discipline: s.key }),
                  }))}
                />
              ) : (
                <p className="ws-note ws-note--empty">
                  Too few postings list a salary in BDT to show a fair median yet ({data.salary.samples} so far). Most
                  employers here don&apos;t publish pay.
                </p>
              )}
            </Panel>

            <Panel eyebrow="Fresh from the web" title="Latest openings" aside={<Link to={jobsLink(scope)}>All jobs →</Link>} className="ws-panel--latest">
              <ul className="ws-latest">
                {data.latest.map((job) => {
                  const apply = safeHref(job.apply_url);
                  return (
                    <li key={job.id}>
                      <span className="ws-latest__mark" aria-hidden="true">{job.company.slice(0, 1)}</span>
                      <Link to={`/jobs/${job.id}`} className="ws-latest__main">
                        <strong>{job.title}</strong>
                        <span>{job.company} · {job.location || WORKPLACES[job.workplace]} · <em>{WORKPLACES[job.workplace]}</em></span>
                      </Link>
                      {apply && <a href={apply} target="_blank" rel="noopener noreferrer" className="ws-latest__apply">Apply ↗</a>}
                    </li>
                  );
                })}
              </ul>
            </Panel>
          </div>

          <p className="ws-method">
            Computed from Prottoy&apos;s open listings: company career boards, public job APIs and jobs posted here. These
            are signals from the roles Prottoy tracks, not national labour statistics. Salaries come only from postings
            that state one.
          </p>
        </div>
      )}

      {official?.available && <OfficialStats data={official} />}
    </div>
  );
}
