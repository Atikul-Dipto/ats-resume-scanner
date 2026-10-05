import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import ThemeSwitcher from "./ThemeSwitcher.jsx";

export default function NavBar({ themeId, onThemeChange }) {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <nav className="navbar" aria-label="Main">
      <NavLink to="/" className="navbar__brand">ATS<span>://</span>Resume</NavLink>
      <div className="navbar__links">
        <NavLink to="/" end>Scan</NavLink>
        <NavLink to="/builder">Builder</NavLink>
        {status === "authenticated" && <NavLink to="/resumes">My resumes</NavLink>}
      </div>
      <div className="navbar__right">
        <ThemeSwitcher activeId={themeId} onChange={onThemeChange} />
        {status === "authenticated" ? (
          <button type="button" className="btn-ghost btn-small" title={user.email}
            onClick={() => { logout(); navigate("/"); }}>
            Sign out
          </button>
        ) : (
          <NavLink to="/login" className="btn-ghost btn-small navbar__signin">Sign in</NavLink>
        )}
      </div>
    </nav>
  );
}
