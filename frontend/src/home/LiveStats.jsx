import { useEffect, useState } from "react";
import { stats as fetchStats } from "../api/client.js";
import useCountUp from "../hooks/useCountUp.js";

const REFRESH_MS = 30_000;

function Stat({ value, label, hint }) {
  const shown = useCountUp(value);
  return (
    <div className="live-stat">
      <strong>{value == null ? "—" : shown.toLocaleString()}</strong>
      <span>{label}</span>
      {hint && <em>{hint}</em>}
    </div>
  );
}

export default function LiveStats() {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | live | offline

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetchStats()
        .then((d) => {
          if (cancelled) return;
          setData(d);
          setState("live");
        })
        .catch(() => !cancelled && setState((s) => (s === "live" ? "live" : "offline")));
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <section className="live-stats hud-panel reveal" aria-live="polite">
      <span className={`live-pill live-pill--${state}`}>
        <i aria-hidden="true" />
        {state === "live" ? "Live" : state === "loading" ? "Connecting…" : "Server waking up…"}
      </span>
      <Stat value={data?.open_jobs} label="Open engineering & data jobs" />
      <Stat value={data?.companies_hiring} label="Companies hiring" />
      <Stat value={data?.local_jobs} label="Posted in Bangladesh" />
      <Stat value={data?.resume_scans} label="Resumes scanned" />
    </section>
  );
}
