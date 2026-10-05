import { useEffect, useState } from "react";

export default function ScoreGauge({ score, label = "ATS SCORE" }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const target = Math.max(0, Math.min(100, score));

  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    let raf;
    const start = performance.now();
    const durationMs = 900;

    const tick = (now) => {
      // rAF timestamps can precede `start` slightly; clamp so the gauge never reads negative.
      const progress = Math.min(Math.max((now - start) / durationMs, 0), 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(target * eased);
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  const offset = circumference - (displayed / 100) * circumference;
  const tier = target >= 80 ? "good" : target >= 55 ? "fair" : "poor";

  return (
    <div className={`score-gauge tier-${tier}`}>
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} className="gauge-track" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          className="gauge-fill"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 70 70)"
        />
      </svg>
      <div className="gauge-center">
        <span className="gauge-value">{Math.round(displayed)}</span>
        <span className="gauge-label">{label}</span>
      </div>
    </div>
  );
}
