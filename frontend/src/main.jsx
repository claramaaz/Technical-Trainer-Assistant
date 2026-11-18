import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";   // self-hosted: no request to an outside font server (NFR-001)
import AuthGate from "./AuthGate.jsx";
import "./theme.css";
import "./layout.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuthGate />
  </StrictMode>
);
