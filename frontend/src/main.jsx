import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AuthGate from "./AuthGate.jsx";
import "./styles.css";
import "./auth.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuthGate />
  </StrictMode>
);
