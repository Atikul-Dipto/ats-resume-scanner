import { useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import Hero3D from "../home/Hero3D.jsx";
import JobFeed from "../home/JobFeed.jsx";
import LiveStats from "../home/LiveStats.jsx";
import useReveal from "../hooks/useReveal.js";
import { useAssistantPage } from "../assistant/AssistantContext.jsx";

const FLOATING = [
  { to: "/scan", icon: "⌕", title: "ATS Resume Scanner", text: "Check compatibility & fix issues", pos: "a" },
  { to: "/builder", icon: "✎", title: "Live Resume Builder", text: "Score updates as you type", pos: "b" },
  { to: "/jobs", icon: "◎", title: "Smart Job Matching", text: "Roles ranked for your profile", pos: "c" },
  { to: "/jobs", icon: "↗", title: "1-Click Apply", text: "Straight to the original posting", pos: "d" },
];

const FEATURES = [
  { icon: "◎", title: "Beat the ATS", text: "Find the formatting, section and keyword problems that get resumes filtered out before a human reads them." },
  { icon: "✦", title: "Fix it live", text: "Edit in a structured builder and watch your score change with every bullet. Export a clean PDF or DOCX." },
  { icon: "▣", title: "More opportunities", text: "Engineering & data jobs from company career boards, job APIs and local employers — in one place." },
  { icon: "➚", title: "Apply in one click", text: "Every listing links to its original application page, ranked by how well it fits your resume." },
];

const STEPS = [
  { n: "01", title: "Scan your resume", text: "Upload a PDF or DOCX. See your ATS score, the exact lines holding you back, and missing keywords." },
  { n: "02", title: "Fix it in the builder", text: "Your resume opens pre-filled. Coaching appears under each weak bullet as the score updates live." },
  { n: "03", title: "Match & apply", text: "Every job is ranked against your resume with the skills gap shown. Apply on the original site in one click." },
];

export default function HomePage() {
  useAssistantPage({ page: "home" });
  const navigate = useNavigate();
  const rootRef = useRef(null);
  useReveal(rootRef);

  return (
    <div className="home" ref={rootRef}>
      <section className="hero">
        <div className="hero__copy">
          <span className="app-eyebrow hero__badge"><i aria-hidden="true">✦</i> The career center for job seekers in Bangladesh</span>
          <h1 className="hero__title">
            Your resume.<br />
            Sharper. Faster.<br />
            <span className="gradient-text">Job ready.</span>
          </h1>
          <p className="hero__lead">
            Scan your resume for ATS problems, fix it with a live score, and discover engineering and data jobs
            matched to you — then apply on the original site in one click.
          </p>
          <div className="hero__ctas">
            <Link to="/scan" className="button-link">Upload your resume →</Link>
            <Link to="/jobs" className="btn-ghost hero__ghost">Browse jobs</Link>
          </div>
          <ul className="hero__checks">
            {["ATS check", "Live builder", "Job matching", "1-click apply"].map((c) => <li key={c}>{c}</li>)}
          </ul>
        </div>

        <div className="hero__visual">
          <Hero3D score={92} onCardClick={() => navigate("/scan")} />
          {FLOATING.map((f, i) => (
            <Link key={f.title} to={f.to} className={`float-card float-card--${f.pos}`} style={{ "--i": i }}>
              <span className="float-card__icon" aria-hidden="true">{f.icon}</span>
              <span>
                <strong>{f.title}</strong>
                <small>{f.text}</small>
              </span>
            </Link>
          ))}
        </div>
      </section>

      <div className="home__section">
        <LiveStats />
      </div>

      <section className="home__section features">
        {FEATURES.map((f, i) => (
          <article key={f.title} className="feature reveal" style={{ "--reveal-delay": `${i * 90}ms` }}>
            <span className="feature__icon" aria-hidden="true">{f.icon}</span>
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </article>
        ))}
      </section>

      <section className="home__section home__split">
        <div className="reveal">
          <span className="app-eyebrow">Live job feed</span>
          <h2>Fresh roles, refreshed while you watch</h2>
          <p className="home__muted">
            New engineering and data openings stream in from company career boards and job APIs every few hours,
            plus jobs posted directly by employers in Bangladesh. Each one links to its original application page.
          </p>
          <Link to="/jobs" className="button-link">See all jobs →</Link>
        </div>
        <div className="hud-panel home__feed reveal" style={{ "--reveal-delay": "120ms" }}>
          <JobFeed />
        </div>
      </section>

      <section className="home__section">
        <div className="home__heading reveal">
          <span className="app-eyebrow">How it works</span>
          <h2>From resume to interview-ready in three steps</h2>
        </div>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.n} className="step hud-panel reveal" style={{ "--reveal-delay": `${i * 120}ms` }}>
              <span className="step__n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="home__section">
        <div className="employers hud-panel reveal">
          <div>
            <span className="app-eyebrow">For employers</span>
            <h2>Hiring engineers or analysts?</h2>
            <p className="home__muted">
              Employer accounts with self-serve job posting are on the way. Your openings will reach candidates
              already matched to your requirements.
            </p>
          </div>
          <span className="employers__soon">Coming soon</span>
        </div>
      </section>
    </div>
  );
}
