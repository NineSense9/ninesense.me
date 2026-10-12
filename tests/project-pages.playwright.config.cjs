const path = require('node:path');
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: 'project-pages-e2e.spec.js',
  timeout: 30_000,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8124',
    channel: 'chrome',
    headless: true,
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure'
  },
  webServer: {
    command: 'server\\.venv\\Scripts\\python.exe -m http.server 8124 --bind 127.0.0.1 --directory site',
    cwd: path.resolve(__dirname, '..'),
    url: 'http://127.0.0.1:8124',
    reuseExistingServer: false
  }
});
