const ROWS = [
  { key: "formatting_score", label: "Formatting" },
  { key: "content_score", label: "Content" },
  { key: "keyword_score", label: "Keyword match" },
];

export default function ScoreBreakdown({ result }) {
  return (
    <div className="score-breakdown">
      {ROWS.map(({ key, label }) => {
        const value = Math.round(result[key]);
        return (
          <div className="breakdown-row" key={key}>
            <div className="breakdown-label">
              <span>{label}</span>
              <span>{value}</span>
            </div>
            <div className="breakdown-track">
              <div className="breakdown-fill" style={{ width: `${value}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
