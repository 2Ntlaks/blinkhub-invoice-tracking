import { defineConfig, devices } from "@playwright/test";

// The journeys share one seeded database and change it (approve, pay, submit), so they run in
// order in a single worker. E2E uses its own ports (API 8011, UI 5183) so it never collides with
// dev servers, or with Windows services that sometimes hold port 8000.
const API_PORT = "8011";
const UI_PORT = "5183";
const recordVideo = process.env.E2E_VIDEO === "1";

const reporters: NonNullable<Parameters<typeof defineConfig>[0]["reporter"]> = [
  ["list"],
  ["html", { open: "never" }],
];
if (process.env.E2E_JSON_REPORT) {
  reporters.push(["json", { outputFile: process.env.E2E_JSON_REPORT }]);
}

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: recordVideo ? 60_000 : 30_000,
  expect: { timeout: 7_000 },
  reporter: reporters,
  use: {
    baseURL: `http://localhost:${UI_PORT}`,
    viewport: { width: 1366, height: 768 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...(recordVideo
      ? {
          video: { mode: "on" as const, size: { width: 1366, height: 768 } },
          launchOptions: { slowMo: 400 },
        }
      : {}),
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 768 } } }],
  webServer: [
    {
      command: "node start-backend.mjs",
      url: `http://localhost:${API_PORT}/api/health`,
      env: { E2E_API_PORT: API_PORT },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm --prefix ../frontend run dev -- --port ${UI_PORT} --strictPort`,
      url: `http://localhost:${UI_PORT}`,
      env: { API_PROXY_TARGET: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
