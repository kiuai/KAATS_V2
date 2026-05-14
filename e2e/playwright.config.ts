import { defineConfig, devices } from '@playwright/test'

/**
 * KAATS Playwright E2E configuration.
 *
 * Targets the docker-compose stack:
 *   API      → http://localhost:8000
 *   Frontend → http://localhost:5173
 *
 * Run against a local dev stack:
 *   cd e2e && npm ci && npm test
 *
 * Run against a custom base URL:
 *   BASE_URL=https://staging.kaats.kiu.ai npm test
 */

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173'
const API_URL  = process.env.API_URL  ?? 'http://localhost:8000'

export default defineConfig({
  testDir: './tests',
  outputDir: '../playwright-results',
  reporter: [
    ['html', { outputFolder: '../playwright-report', open: 'never' }],
    ['list'],
  ],

  // Retry once on CI to tolerate flaky timing issues.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,

  // Global test timeout
  timeout: 30_000,
  expect: { timeout: 8_000 },

  use: {
    baseURL: BASE_URL,
    // Pass the API URL via env so fixtures can call it directly.
    extraHTTPHeaders: {},
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Uncomment to also run on Firefox/WebKit in CI:
    // { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    // { name: 'webkit',  use: { ...devices['Desktop Safari']  } },
  ],
})

export { API_URL }
