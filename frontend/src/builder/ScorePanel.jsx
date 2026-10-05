import ScoreGauge from "../components/ScoreGauge.jsx";
import FormattingIssues from "../components/FormattingIssues.jsx";
import KeywordPanel from "../components/KeywordPanel.jsx";
import SuggestionsList from "../components/SuggestionsList.jsx";

const ROWS = [
  { key: "formatting_score", label: "Structure" },
  { key: "content_score", label: "Content" },
  { key: "keyword_score", label: "Keywords" },
];

export default function ScorePanel({ score, pending, error, jobDescription, onJobDescriptionChange }) {
  return (
    <div className="score-panel">
      <div className="score-panel__head">
        {score ? <ScoreGauge score={score.ats_score} label="LIVE SCORE" /> : <div className="score-panel__placeholder">…</div>}
        <div className="score-breakdown">
          {ROWS.map(({ key, label }) => {
            const value = score ? Math.round(score[key]) : 0;
            return (
              <div className="breakdown-row" key={key}>
                <div className="breakdown-label">
                  <span>{label}</span>
                  <span>{score ? value : "–"}</span>
                </div>
                <div className="breakdown-track">
                  <div className="breakdown-fill" style={{ width: `${value}%` }} />
                </div>
              </div>
            );
          })}
          <p className={`score-status ${pending ? "is-pending" : ""}`} aria-live="polite">
            {error ? `⚠ ${error}` : pending ? "Re-scoring…" : "Up to date"}
          </p>
        </div>
      </div>

      <div className="score-panel__section">
        <label className="jd-label" htmlFor="builder-jd">
          Target job <span>(paste a posting to tailor keywords)</span>
        </label>
        <textarea id="builder-jd" rows={4} value={jobDescription} onChange={(e) => onJobDescriptionChange(e.target.value)}
          placeholder="Paste the job description you're applying to…" />
      </div>

      {score && (
        <>
          {(jobDescription.trim() || score.keywords.matched.length > 0) && (
            <div className="score-panel__section">
              <h3>Keywords</h3>
              <KeywordPanel keywords={score.keywords} />
            </div>
          )}
          <div className="score-panel__section">
            <h3>Fix next</h3>
            <FormattingIssues issues={score.formatting_issues} emptyText="Structure looks complete — nothing to fix here." />
          </div>
          <div className="score-panel__section">
            <h3>Suggestions</h3>
            <SuggestionsList suggestions={score.suggestions} />
          </div>
        </>
      )}
    </div>
  );
}
