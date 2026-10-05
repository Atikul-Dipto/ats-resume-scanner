import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export function Logo() {
  return (
    <span className="logo" aria-label="Prottoy">
      <span className="logo__mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" width="18" height="18">
          <path d="M10 25V7h7a6 6 0 0 1 0 12h-4" fill="none" stroke="currentColor" strokeWidth="3.4"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="logo__text">Prottoy</span>
    </span>
  );
}

export default function NavBar({ mode, onModeChange }) {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    ["/", "Home", true],
    ["/scan", "Scan"],
    ["/builder", "Builder"],
    ["/jobs", "Jobs"],
    ...(status === "authenticated" ? [["/resumes", "My resumes"]] : []),
    ...(user?.is_admin ? [["/admin/jobs", "Admin"]] : []),
  ];

  return (
    <header className={`navbar ${scrolled ? "is-scrolled" : ""} ${open ? "is-open" : ""}`}>
      <nav className="navbar__inner" aria-label="Main">
        <Link to="/" className="navbar__brand"><Logo /></Link>
        <div className="navbar__links" id="main-menu">
          {links.map(([to, label, end]) => (
            <NavLink key={to} to={to} end={end}>{label}</NavLink>
          ))}
        </div>
        <div className="navbar__right">
          <ThemeToggle mode={mode} onChange={onModeChange} />
          {status === "authenticated" ? (
            <button type="button" className="btn-ghost btn-small" title={user.email}
              onClick={() => { logout(); navigate("/"); }}>
              Sign out
            </button>
          ) : (
            <>
              <NavLink to="/login" className="navbar__login">Log in</NavLink>
              <Link to="/scan" className="button-link button-link--small">Get started</Link>
            </>
          )}
          <button type="button" className="navbar__burger icon-btn" aria-expanded={open} aria-controls="main-menu"
            aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen((o) => !o)}>
            <span /><span /><span />
          </button>
        </div>
      </nav>
    </header>
  );
}
