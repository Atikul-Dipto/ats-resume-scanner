import ScoreGauge from "./ScoreGauge.jsx";
import ScoreBreakdown from "./ScoreBreakdown.jsx";
import SectionsChecklist from "./SectionsChecklist.jsx";
import FormattingIssues from "./FormattingIssues.jsx";
import KeywordPanel from "./KeywordPanel.jsx";
import SuggestionsList from "./SuggestionsList.jsx";
import JobSearchPanel from "./JobSearchPanel.jsx";

export default function ResultsPanel({ result, onReset }) {
  return (
    <div className="results-panel">
      <div className="results-header">
        <ScoreGauge score={result.ats_score} />
        <ScoreBreakdown result={result} />
      </div>

      <div className="results-grid">
        <section>
          <h3>Sections</h3>
          <SectionsChecklist sections={result.sections} />
        </section>

        <section>
          <h3>Formatting</h3>
          <FormattingIssues issues={result.formatting_issues} />
        </section>

        <section className="span-2">
          <h3>Keywords</h3>
          <KeywordPanel keywords={result.keywords} />
        </section>

        <section className="span-2">
          <h3>Suggestions</h3>
          <SuggestionsList suggestions={result.suggestions} />
        </section>

        <section className="span-2">
          <h3>Find matching jobs</h3>
          <JobSearchPanel profile={result.profile} />
        </section>
      </div>

      <button className="reset-button" onClick={onReset}>
        Scan another resume
      </button>
    </div>
  );
}
