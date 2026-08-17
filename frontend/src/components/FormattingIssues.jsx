export default function FormattingIssues({ issues }) {
  if (issues.length === 0) {
    return <p className="no-issues">No formatting issues detected.</p>;
  }

  return (
    <ul className="issues-list">
      {issues.map((issue, i) => (
        <li key={i} className={`severity-${issue.severity}`}>
          <span className="severity-badge">{issue.severity}</span>
          {issue.message}
        </li>
      ))}
    </ul>
  );
}
