export default function KeywordPanel({ keywords }) {
  return (
    <div className="keyword-panel">
      <div>
        <h4>Matched ({keywords.matched.length})</h4>
        <div className="chip-list">
          {keywords.matched.length === 0 && <span className="chip-empty">None found</span>}
          {keywords.matched.map((k) => (
            <span className="chip chip-matched" key={k}>
              {k}
            </span>
          ))}
        </div>
      </div>
      {keywords.missing.length > 0 && (
        <div>
          <h4>Missing ({keywords.missing.length})</h4>
          <div className="chip-list">
            {keywords.missing.map((k) => (
              <span className="chip chip-missing" key={k}>
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
