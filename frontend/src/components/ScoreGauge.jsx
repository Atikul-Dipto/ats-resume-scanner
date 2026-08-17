export default function ScoreGauge({ score, label = "ATS Score" }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference - (clamped / 100) * circumference;
  const tier = clamped >= 80 ? "good" : clamped >= 55 ? "fair" : "poor";

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
        <span className="gauge-value">{Math.round(clamped)}</span>
        <span className="gauge-label">{label}</span>
      </div>
    </div>
  );
}
