import ScoreGauge from "./ScoreGauge.jsx";
import ScoreBreakdown from "./ScoreBreakdown.jsx";
import SectionsChecklist from "./SectionsChecklist.jsx";
import FormattingIssues from "./FormattingIssues.jsx";
import KeywordPanel from "./KeywordPanel.jsx";
import SuggestionsList from "./SuggestionsList.jsx";
import FlaggedLines from "./FlaggedLines.jsx";
import JobSearchPanel from "./JobSearchPanel.jsx";

export default function ResultsPanel({ result, onReset, onOpenInBuilder }) {
  return (
    <div className="results-panel">
      <div className="results-header">
        <ScoreGauge score={result.ats_score} />
        <ScoreBreakdown result={result} />
        {onOpenInBuilder && (
          <div className="results-cta">
            <p>Fix these issues in the builder — we&apos;ve pre-filled it from your file, with a live score as you edit.</p>
            <button type="button" onClick={onOpenInBuilder}>Open in builder →</button>
          </div>
        )}
      </div>

      <div className="results-grid">
        <section>
          <h3>
            <span className="section-icon">§</span>Sections
          </h3>
          <SectionsChecklist sections={result.sections} />
        </section>

        <section>
          <h3>
            <span className="section-icon">◉</span>Formatting Scan
          </h3>
          <FormattingIssues issues={result.formatting_issues} />
        </section>

        <section className="span-2">
          <h3>
            <span className="section-icon">✎</span>Flagged Content
          </h3>
          <FlaggedLines lines={result.flagged_lines} />
        </section>

        <section className="span-2">
          <h3>
            <span className="section-icon">#</span>Keywords
          </h3>
          <KeywordPanel keywords={result.keywords} />
        </section>

        <section className="span-2">
          <h3>
            <span className="section-icon">►</span>Suggestions
          </h3>
          <SuggestionsList suggestions={result.suggestions} />
        </section>

        <section className="span-2">
          <h3>
            <span className="section-icon">⌕</span>Find Matching Jobs
          </h3>
          <JobSearchPanel profile={result.profile} />
        </section>
      </div>

      <button className="reset-button" onClick={onReset}>
        Scan Another Resume
      </button>
    </div>
  );
}
