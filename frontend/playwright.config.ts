import { defineConfig } from "@playwright/test";

// The e2e runs against the FastAPI server serving the built SPA — i.e. exactly
// how production works (one origin, no dev proxy). Build first, then:
//   cd backend && uvicorn app.main:app --port 8020
// The backend must run with DEV_LOGIN=true and a TMDB_API_KEY.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8020",
    trace: "retain-on-failure",
  },
  reporter: [["list"]],
});
