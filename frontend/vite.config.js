import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the browser talks to Vite; Vite forwards the API calls to FastAPI.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/search": backend,
      "/figures": backend,
    },
  },
  build: {
    // the page Vite builds.
    rollupOptions: { input: "index.html" },
  },
});
