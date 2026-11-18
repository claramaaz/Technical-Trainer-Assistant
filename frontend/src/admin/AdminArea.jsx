import { useEffect, useState } from "react";
import { ADMIN_PAGES } from "./adminPages.js";
import PageHead from "./PageHead.jsx";
import Analytics from "./Analytics.jsx";
import QaQueue from "./QaQueue.jsx";
import Sources from "./Sources.jsx";
import "./qa.css";

// The admin screens (P7-36). The sidebar is shown by AuthGate only to Admin accounts, but that is a
// convenience: before showing anything, this component asks the SERVER (GET /admin/ping, P7-35).
// A 403 shows "Admin role required" and a 401 sends back to the login page, whatever the browser
// believes the role is (BR-003).
export default function AdminArea({ route, onSessionExpired }) {
  const [access, setAccess] = useState("checking"); // checking | allowed | forbidden | error

  useEffect(() => {
    let cancelled = false;
    fetch("/admin/ping")
      .then((r) => {
        if (cancelled) return;
        if (r.status === 401) onSessionExpired?.();
        else setAccess(r.ok ? "allowed" : r.status === 403 ? "forbidden" : "error");
      })
      .catch(() => !cancelled && setAccess("error"));
    return () => {
      cancelled = true;
    };
  }, [onSessionExpired]);

  if (access === "checking") return <p className="admin-status">Checking access…</p>;
  if (access === "forbidden")
    return <p className="admin-status notice notice-error" role="alert">Admin role required. This account can only use the chat.</p>;
  if (access === "error")
    return (
      <p className="admin-status notice notice-error" role="alert">
        Could not reach the server. Check your connection and try again.
      </p>
    );

  const page = ADMIN_PAGES.find((p) => p.path === route);
  if (!page) return <p className="admin-status">This page does not exist. Choose a page in the menu.</p>;
  if (page.path === "/admin/sources") return <Sources page={page} onSessionExpired={onSessionExpired} />;
  if (page.path === "/admin/qa") return <QaQueue page={page} onSessionExpired={onSessionExpired} />;
  if (page.path === "/admin/analytics") return <Analytics page={page} onSessionExpired={onSessionExpired} />;
  return <AdminPage page={page} />;
}

function AdminPage({ page }) {
  return (
    <section className="admin-page">
      <PageHead page={page} />
      <div className="admin-empty" role="status">
        <strong>Not built yet.</strong> {page.empty}
      </div>
      <h2 className="admin-subtitle">What you will be able to do here</h2>
      <ul className="admin-list">
        {page.willDo.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="admin-req">Requirements: {page.requirement}</p>
    </section>
  );
}
