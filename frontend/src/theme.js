export const THEMES = [
  {
    id: "neural",
    label: "Neural",
    accent: "#22e4ff",
    accent2: "#7c5cff",
    accentRgb: "34, 228, 255",
  },
  {
    id: "cyber",
    label: "Cyber",
    accent: "#ff2e97",
    accent2: "#a855f7",
    accentRgb: "255, 46, 151",
  },
  {
    id: "matrix",
    label: "Matrix",
    accent: "#39ff9d",
    accent2: "#22e4ff",
    accentRgb: "57, 255, 157",
  },
  {
    id: "terminal",
    label: "Amber",
    accent: "#ffb020",
    accent2: "#ff5f5f",
    accentRgb: "255, 176, 32",
  },
];

export const DEFAULT_THEME_ID = "neural";
export const THEME_STORAGE_KEY = "ats-scanner-theme";

export function getStoredThemeId() {
  if (typeof window === "undefined") return DEFAULT_THEME_ID;
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return THEMES.some((t) => t.id === stored) ? stored : DEFAULT_THEME_ID;
}

export function applyTheme(themeId) {
  const theme = THEMES.find((t) => t.id === themeId) || THEMES[0];
  const root = document.documentElement;
  root.style.setProperty("--accent", theme.accent);
  root.style.setProperty("--accent-2", theme.accent2);
  root.style.setProperty("--accent-rgb", theme.accentRgb);
  root.dataset.theme = theme.id;
  window.localStorage.setItem(THEME_STORAGE_KEY, theme.id);
}
