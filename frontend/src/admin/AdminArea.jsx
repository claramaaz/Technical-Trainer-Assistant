import { useEffect, useState } from "react";
import { ADMIN_PAGES } from "./adminPages.js";

// The admin screens (P7-36). The menu is shown by AuthGate only to Admin accounts, but that is
// a convenience: before showing anything, this component asks the SERVER (GET /admin/ping,
// P7-35). A 403 shows "Admin role required" and a 401 sends back to the login page, whatever
// the browser believes the role is (BR-003).
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
    return (
      <p className="admin-status admin-denied" role="alert">
        Admin role required. This account can only use the search page.
      </p>
    );
  if (access === "error")
    return (
      <p className="admin-status admin-denied" role="alert">
        Could not reach the server. Check your connection and try again.
      </p>
    );

  const page = ADMIN_PAGES.find((p) => p.path === route);
  return page ? <AdminPage page={page} /> : <AdminOverview />;
}

function AdminOverview() {
  return (
    <section className="admin-page">
      <h1>Administration</h1>
      <p className="admin-lead">
        Load and check the handbooks, fix figures that were extracted or matched wrongly, and watch
        how the system is used.
      </p>
      <div className="admin-cards">
        {ADMIN_PAGES.map((p) => (
          <a key={p.path} className="admin-card" href={`#${p.path}`}>
            <h2>{p.title}</h2>
            <p>{p.purpose}</p>
            <span className="admin-req">{p.requirement}</span>
          </a>
        ))}
      </div>
    </section>
  );
}

function AdminPage({ page }) {
  return (
    <section className="admin-page">
      <h1>{page.title}</h1>
      <p className="admin-lead">{page.purpose}</p>
      <div className="admin-empty" role="status">
        <strong>Nothing to show yet.</strong> {page.empty}
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
