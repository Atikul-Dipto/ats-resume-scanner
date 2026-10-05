export default function ThemeToggle({ mode, onChange }) {
  const dark = mode === "dark";
  return (
    <button
      type="button"
      className={`theme-toggle ${dark ? "is-dark" : ""}`}
      onClick={() => onChange(dark ? "light" : "dark")}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
    >
      <span className="theme-toggle__track" aria-hidden="true">
        <span className="theme-toggle__thumb">{dark ? "☾" : "☀"}</span>
      </span>
    </button>
  );
}
