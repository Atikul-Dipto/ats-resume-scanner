export default function SectionsChecklist({ sections }) {
  return (
    <ul className="sections-list">
      {sections.map((s) => (
        <li key={s.name} className={s.found ? "found" : "missing"}>
          <span className="check-icon">{s.found ? "✓" : "✗"}</span>
          {s.name}
        </li>
      ))}
    </ul>
  );
}
