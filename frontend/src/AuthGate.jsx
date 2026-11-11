import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import AdminArea from "./admin/AdminArea.jsx";
import { ADMIN_PAGES } from "./admin/adminPages.js";
import "./admin/admin.css";
import useHashRoute, { navigate } from "./useHashRoute.js";

// Login screen and session bar around the search page (P7-35; FR-004, UC-05).
//
// The login token lives in an httpOnly cookie set by the server: this code never sees or
// stores it, so nothing in localStorage can be stolen. Whether the user is logged in is
// asked to the server (GET /me). Hiding screens here is only for convenience: the server
// refuses every protected request on its own (401 / 403), whatever this page shows.
//
// P7-36: after login an Admin lands on the admin overview and a Learner on the search page
// (UC-05 step 4). Only Admins see the admin menu; the admin pages also ask the server.
export default function AuthGate() {
  const route = useHashRoute();
  // session: undefined = still asking the server, null = logged out, {email, role} = logged in
  const [session, setSession] = useState(undefined);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/me")
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((user) => !cancelled && setSession(user));
    return () => {
      cancelled = true;
    };
  }, []);

  async function logout() {
    await fetch("/logout", { method: "POST" }).catch(() => {});
    setNotice("");
    setSession(null);
  }

  // useCallback: the same function on every render, so AdminArea does not re-check access
  // each time this component re-renders.
  const sessionExpired = useCallback(() => {
    setNotice("Your session has ended. Please log in again.");
    setSession(null);
  }, []);

  if (session === undefined) return <p className="auth-loading">Loading…</p>;

  if (session === null) {
    return (
      <LoginForm
        notice={notice}
        onLoggedIn={(user) => {
          setNotice("");
          setSession(user);
          navigate(user.role === "admin" ? "/admin" : "/");
        }}
      />
    );
  }

  return (
    <>
      <div className="session-bar">
        <span className="session-user">
          {session.email}
          <span className={`role-badge role-${session.role}`}>
            {session.role === "admin" ? "Admin" : "Learner"}
          </span>
        </span>
        <button type="button" className="logout" onClick={logout}>
          Log out
        </button>
      </div>
      {session.role === "admin" && <AdminNav route={route} />}
      {route.startsWith("/admin") && session.role === "admin" ? (
        <AdminArea route={route} onSessionExpired={sessionExpired} />
      ) : (
        <>
          {route.startsWith("/admin") && (
            <p className="admin-learner-note" role="alert">
              The admin pages are only for Admin accounts.
            </p>
          )}
          <App onSessionExpired={sessionExpired} />
        </>
      )}
    </>
  );
}

function AdminNav({ route }) {
  const links = [
    { path: "/", title: "Search" },
    { path: "/admin", title: "Overview" },
    ...ADMIN_PAGES.map((p) => ({ path: p.path, title: p.title })),
  ];
  return (
    <nav className="admin-nav" aria-label="Admin menu">
      {links.map((l) => (
        <a
          key={l.path}
          href={`#${l.path}`}
          className={route === l.path ? "active" : undefined}
          aria-current={route === l.path ? "page" : undefined}
        >
          {l.title}
        </a>
      ))}
    </nav>
  );
}

function LoginForm({ notice, onLoggedIn }) {
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
        err instanceof TypeError
          ? "Could not reach the server. Check your connection and try again."
          : err.message
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <h1>Technical Training Assistant</h1>
      <p className="login-subtitle">Log in to search the FAA handbooks.</p>
      {notice && <p className="login-notice" role="status">{notice}</p>}
      <form onSubmit={onSubmit} className="login-form">
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
    </main>
  );
}
