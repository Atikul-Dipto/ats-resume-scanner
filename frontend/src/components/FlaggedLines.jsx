export default function FlaggedLines({ lines }) {
  if (lines.length === 0) {
    return <p className="no-issues">No weak bullet points detected — content reads strong.</p>;
  }

  return (
    <ul className="flagged-lines">
      {lines.map((line, i) => (
        <li className="flagged-line" style={{ "--i": i }} key={i}>
          <div className="flagged-line__scan">
            <span className="flagged-line__beam" />
            <code>{line.text}</code>
          </div>
          <div className="flagged-line__reasons">
            {line.reasons.map((reason) => (
              <span className="flagged-line__reason" key={reason}>
                ⚠ {reason}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
