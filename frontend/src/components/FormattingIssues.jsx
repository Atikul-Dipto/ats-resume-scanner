export default function FormattingIssues({ issues, emptyText = "No formatting issues detected." }) {
  if (issues.length === 0) {
    return <p className="no-issues">{emptyText}</p>;
  }

  return (
    <ul className="issues-list">
      {issues.map((issue, i) => (
        <li key={i} className={`severity-${issue.severity}`} style={{ "--i": i }}>
          <div className="issue-head">
            <span className="severity-badge">{issue.severity}</span>
            {issue.location && (
              <span className="location-badge">
                <span className="location-badge__ping" />[ {issue.location.toUpperCase()} ]
              </span>
            )}
          </div>
          {issue.message}
        </li>
      ))}
    </ul>
  );
}
