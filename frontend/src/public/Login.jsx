import { useState } from "react";
import { LogoMark } from "../Logo.jsx";
import "./public.css";

// The ONE login page (P7-35; FR-004, UC-05). The role comes from the account, never from the page:
// there is no "log in as admin" choice and no sign-up (an open sign-up would let anyone become Admin).
export default function Login({ notice, onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (response.status === 401 || response.status === 422) {
        setError("Wrong email or password."); // UC-05 A1: generic, does not say which one
        return;
      }
      if (!response.ok) throw new Error(`The server answered with an error (${response.status}).`);
      const user = await response.json();
      setPassword("");
      onLoggedIn({ email: user.email, role: user.role });
    } catch (err) {
      setError(
        err instanceof TypeError ? "Could not reach the server. Check your connection and try again." : err.message
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <main className="login-card">
        <a href="#/" className="login-logo" aria-label="FlightWise home">
          <LogoMark size={40} />
        </a>
        <h1>Log in to FlightWise</h1>
        <p className="login-sub">Technical Training Assistant</p>
        {notice && <p className="notice notice-info" role="status">{notice}</p>}
        <form onSubmit={onSubmit} className="login-form">
          <label className="field">
            Email
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="notice notice-error" role="alert">{error}</p>}
          <button type="submit" className="btn login-submit" disabled={busy}>
            {busy ? "Logging in…" : "Log in"}
          </button>
        </form>
        <p className="login-foot">No account? Ask your instructor to create one.</p>
      </main>
    </div>
  );
}
