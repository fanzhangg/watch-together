import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the FastAPI backend so the browser sees a SINGLE origin
// (design risk #1 — otherwise the session cookie won't be sent). In prod the
// build is served by FastAPI itself, so there is no cross-origin issue.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // FastAPI serves this directory (see backend/app/main.py WEB_DIR).
    outDir: "../backend/app/web",
    emptyOutDir: true,
  },
});
