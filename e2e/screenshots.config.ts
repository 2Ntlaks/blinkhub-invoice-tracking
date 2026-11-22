import base from "./playwright.config";
import { defineConfig } from "@playwright/test";

// Captures README screenshots into docs/screenshots/ from a freshly seeded app.
//   npx playwright test --config screenshots.config.ts
export default defineConfig({
  ...base,
  testDir: "./screenshots",
  reporter: [["list"]],
  use: { ...base.use, viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
  projects: undefined,
});
