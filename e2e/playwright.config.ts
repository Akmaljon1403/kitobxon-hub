import { defineConfig, devices } from '@playwright/test'

// Browser checks of the main member and admin journeys against a real backend and the built
// web apps. Run `python ../e2e/seed.py` in ../backend first (see docs/TESTING.md).
const port = Number(process.env.E2E_PORT ?? 8077)
const python = process.env.E2E_PYTHON ?? 'python'

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    cwd: '../backend',
    url: `http://127.0.0.1:${port}/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: 'pipe',
  },
})
