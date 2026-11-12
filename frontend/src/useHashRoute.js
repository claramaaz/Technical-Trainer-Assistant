import { useEffect, useState } from "react";

// Which screen to show, read from the part of the address after "#" (P7-36).
//   http://localhost:5173/#/admin/coverage  ->  route "/admin/coverage"
//
// Why "#": the browser never sends it to the server, so every screen is served by the same
// index.html, in development (Vite) and when FastAPI serves the build, with no server change
// and no routing library. /admin/... without "#" would also clash with the API routes.
function currentRoute() {
  const path = window.location.hash.replace(/^#/, "");
  return path.startsWith("/") ? path : "/";
}

export function navigate(path) {
  window.location.hash = path;
}

export default function useHashRoute() {
  const [route, setRoute] = useState(currentRoute);
  useEffect(() => {
    const onChange = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
