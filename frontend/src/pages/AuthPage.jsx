import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

export default function AuthPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/resumes";
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(mode, email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const registering = mode === "register";
  return (
    <div className="auth-page">
      <header className="app-header">
        <p className="app-eyebrow">// {registering ? "CREATE ACCOUNT" : "SIGN IN"}</p>
        <h1>{registering ? "Create an account" : "Welcome back"}</h1>
        <p>
          {location.state?.reason === "save"
            ? "Your draft is safe in this browser — sign in to save it to your account."
            : "Accounts are optional. Scanning and building work without one; an account saves resumes across devices."}
        </p>
      </header>

      <form className="auth-form hud-panel" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Email</span>
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Password</span>
          <input type="password" autoComplete={registering ? "new-password" : "current-password"} required
            minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />
          {registering && <span className="field-hint">At least 8 characters.</span>}
        </label>
        {error && <p className="error-text">⚠ {error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Please wait…" : registering ? "Create account" : "Sign in"}</button>
        <button type="button" className="link-button" onClick={() => { setMode(registering ? "login" : "register"); setError(null); }}>
          {registering ? "Already have an account? Sign in" : "New here? Create an account"}
        </button>
      </form>
    </div>
  );
}
