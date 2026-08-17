import { THEMES } from "../theme.js";

export default function ThemeSwitcher({ activeId, onChange }) {
  return (
    <div className="theme-switcher" role="group" aria-label="Color theme">
      {THEMES.map((theme) => (
        <button
          key={theme.id}
          type="button"
          className={`theme-swatch ${activeId === theme.id ? "is-active" : ""}`}
          style={{ "--swatch-color": theme.accent }}
          onClick={() => onChange(theme.id)}
          title={theme.label}
          aria-label={`${theme.label} theme`}
          aria-pressed={activeId === theme.id}
        />
      ))}
    </div>
  );
}
