import { defineConfig } from "@playwright/test";
import { sharedConfig } from "./shared/config";

export default defineConfig({
  ...sharedConfig,
  testDir: ".",
  testMatch: ["specs/**/*.spec.ts", "presets/**/*.spec.ts", "custom_multiseed/**/*.spec.ts", "certificates/**/*.spec.ts"],
});
