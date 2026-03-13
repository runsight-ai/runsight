import { defineConfig, devices } from "@playwright/test";

const isIntegration = process.env.E2E_INTEGRATION === "1";

export default defineConfig({
  testDir: isIntegration ? "./e2e-integration" : "./e2e",
  outputDir: isIntegration ? "./e2e-integration/test-results" : "./e2e/test-results",
  fullyParallel: !isIntegration,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
