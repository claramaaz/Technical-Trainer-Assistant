import { useCallback, useEffect, useState } from "react";
import AdminArea from "./admin/AdminArea.jsx";
import { ADMIN_PAGES } from "./admin/adminPages.js";
import "./admin/admin.css";
import ChatPage from "./chat/ChatPage.jsx";
import { LogoMark, Wordmark } from "./Logo.jsx";
import Landing from "./public/Landing.jsx";
import Login from "./public/Login.jsx";
import useHashRoute, { navigate } from "./useHashRoute.js";

// Which screens a visitor sees (P7-35, P7-36; FR-004, UC-05, BR-003).
//   logged out   landing page (#/) and the ONE login page (#/login)
//   Learner      the chat only (P7-56)
//   Admin        a sidebar: Chat, Sources, QA queue, Coverage, Analytics
// The login token lives in an httpOnly cookie set by the server: this code never sees it. Whether the
// user is logged in is asked to the server (GET /me). Hiding screens here is only for convenience:
// the server refuses every protected request on its own (401 / 403), whatever this page shows.
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
    navigate("/");
  }

  // useCallback: the same function on every render, so the pages do not re-check access each time.
  const sessionExpired = useCallback(() => {
    setNotice("Your session has ended. Please log in again.");
    setSession(null);
    navigate("/login");
  }, []);

  if (session === undefined) {
    return (
      <p className="app-loading" role="status">
        <LogoMark size={28} /> Loading…
      </p>
    );
  }

  if (session === null) {
    if (route !== "/login") return <Landing />;
    return (
      <Login
        notice={notice}
        onLoggedIn={(user) => {
          setNotice("");
          setSession(user);
          navigate(user.role === "admin" ? "/admin/sources" : "/");
        }}
      />
    );
  }

  if (session.role === "admin") {
    return <AdminShell route={route} session={session} onLogout={logout} onSessionExpired={sessionExpired} />;
  }

  return (
    <div className="learner">
      <header className="app-header">
        <a href="#/" className="app-home" aria-label="FlightWise">
          <Wordmark size={26} />
        </a>
        <UserMenu session={session} onLogout={logout} />
      </header>
      {route.startsWith("/admin") && (
        <p className="notice notice-error learner-note" role="alert">
          The admin pages are only for Admin accounts.
        </p>
      )}
      <ChatPage onSessionExpired={sessionExpired} />
    </div>
  );
}

function UserMenu({ session, onLogout }) {
  return (
    <div className="user-menu">
      <span className="user-email" title={session.email}>{session.email}</span>
      <button type="button" className="btn btn-quiet btn-small" onClick={onLogout}>
        Log out
      </button>
    </div>
  );
}

const ADMIN_NAV = [{ path: "/chat", title: "Chat" }, ...ADMIN_PAGES.map((p) => ({ path: p.path, title: p.title }))];

function AdminShell({ route, session, onLogout, onSessionExpired }) {
  useEffect(() => {
    if (route === "/" || route === "/admin" || route === "/login") navigate("/admin/sources");
    // On a phone the menu scrolls sideways: keep the current page's link in view.
    document.querySelector(".sidebar a.active")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [route]);

  const inChat = route === "/chat";
  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <a href="#/admin/sources" className="sidebar-brand" aria-label="FlightWise administration">
          <LogoMark size={26} />
          <span>
            <span className="sidebar-name">FlightWise</span>
            <span className="sidebar-role">Administration</span>
          </span>
        </a>
        <nav aria-label="Admin menu">
          <ul>
            {ADMIN_NAV.map((l) => (
              <li key={l.path}>
                <a
                  href={`#${l.path}`}
                  className={route === l.path ? "active" : undefined}
                  aria-current={route === l.path ? "page" : undefined}
                >
                  {l.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="sidebar-user">
          <span className="user-email" title={session.email}>{session.email}</span>
          <button type="button" className="sidebar-logout" onClick={onLogout}>Log out</button>
        </div>
      </aside>
      <div className="admin-main">
        {inChat ? <ChatPage onSessionExpired={onSessionExpired} /> : <AdminArea route={route} onSessionExpired={onSessionExpired} />}
      </div>
    </div>
  );
}
