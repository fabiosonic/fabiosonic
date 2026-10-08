import "dotenv/config";
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 3100);
const BASE_URL = `http://localhost:${PORT}`;
// Opcional: usar um Chromium já instalado (ex.: ambientes sem download de navegadores).
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { executablePath },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 }, launchOptions: { executablePath } }, testIgnore: /mobile\.spec\.ts/ },
    { name: "celular", use: { ...devices["Pixel 7"], launchOptions: { executablePath } }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: {
    // Build de produção servido contra o banco de TESTE (preparado por `npm run db:test:prepare`).
    command: `npm run build && npx next start -p ${PORT}`,
    url: `${BASE_URL}/api/health`,
    timeout: 300_000,
    reuseExistingServer: !process.env.CI,
    env: {
      DATABASE_URL: process.env.TEST_DATABASE_URL ?? "",
      APP_URL: BASE_URL,
      BETTER_AUTH_URL: BASE_URL,
      APP_ENV: "demo",
      EMAIL_TRANSPORT: "dev",
      AUTH_RATE_LIMIT_SIGNIN_MAX: "1000",
      AUTH_RATE_LIMIT_RESET_MAX: "1000",
      LOG_LEVEL: "warn",
    },
  },
});
