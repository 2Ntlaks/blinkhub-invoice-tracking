import { defineConfig, devices } from "@playwright/test";

// The journeys share one seeded database and change it (approve, pay, submit), so they run in
// order in a single worker. Stop any dev servers on ports 8000/5173 before running.
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1366, height: 768 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 768 } } }],
  webServer: [
    {
      command: "node start-backend.mjs",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm --prefix ../frontend run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
