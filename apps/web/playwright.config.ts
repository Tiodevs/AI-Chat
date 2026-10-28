import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  webServer: {
    command: "pnpm dev --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: "mobile",
      testIgnore: /motion\.spec\.ts/,
      use: {
        ...devices["Pixel 5"],
        reducedMotion: "reduce",
      },
    },
    {
      name: "animation",
      testMatch: /motion\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        reducedMotion: "no-preference",
      },
    },
  ],
})
