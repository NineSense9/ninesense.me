const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  testMatch: ["guestbook-e2e.spec.js", "admin-foundation-e2e.spec.js"],
  timeout: 60_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8123",
    channel: "chrome",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: "server\\.venv\\Scripts\\python.exe tests\\e2e_server.py",
    url: "http://127.0.0.1:8123/api/health",
    reuseExistingServer: false,
    timeout: 30_000
  }
});
