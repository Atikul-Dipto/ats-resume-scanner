export default function SuggestionsList({ suggestions }) {
  if (suggestions.length === 0) {
    return <p className="no-issues">Nothing to flag — this resume looks solid.</p>;
  }

  return (
    <ul className="suggestions-list">
      {suggestions.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ul>
  );
}
