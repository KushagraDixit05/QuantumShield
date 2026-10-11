// Shared Playwright settings. Lead-owned: subagents request changes in docs/status/gaps-<agent>.md.
// Own servers on 8011/3001 so the suite never touches whatever holds 8000/3000.
// (CORS in backend/main.py allows localhost/127.0.0.1 on :3000 and :3001 only.)
import type { PlaywrightTestConfig } from "@playwright/test";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

export const API_PORT = 8011;
export const WEB_PORT = 3001;
export const ROOT = path.resolve(__dirname, "../../..");

// /opt/pw-browsers does not exist on this machine; the pre-installed Chromium is in ~/.cache/ms-playwright.
// CHROMIUM_PATH overrides. Never run `playwright install`.
export function findChromium(): string | undefined {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  for (const base of ["/opt/pw-browsers", path.join(homedir(), ".cache", "ms-playwright")]) {
    if (!existsSync(base)) continue;
    for (const d of readdirSync(base).sort().reverse()) {
      for (const rel of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const p = path.join(base, d, rel);
        if (d.startsWith("chromium-") && existsSync(p)) return p;
      }
    }
  }
  return undefined;
}

export const sharedConfig: PlaywrightTestConfig = {
  timeout: 240_000,
  expect: { timeout: 20_000 },
  workers: 1, // RAM is 7.5 GB: one browser at a time
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    headless: true,
    launchOptions: { executablePath: findChromium(), args: ["--no-sandbox"] },
  },
  webServer: [
    {
      command: `${ROOT}/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run build && npx next start -p ${WEB_PORT}`,
      cwd: path.join(ROOT, "frontend"),
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}` },
      url: `http://127.0.0.1:${WEB_PORT}/`,
      reuseExistingServer: false,
      timeout: 240_000,
    },
  ],
};
