import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: process.env.DASHBOARD_URL || "http://127.0.0.1:18089",
    headless: true,
    launchOptions: { executablePath: process.env.CHROMIUM_PATH },
  },
  workers: 1,
  reporter: "list",
});
