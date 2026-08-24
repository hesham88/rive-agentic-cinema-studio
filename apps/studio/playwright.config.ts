import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  // Rive loads WASM and paints on a canvas; give it room on a cold start.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // One worker on purpose. Every test mounts a WebGL context and a WASM
  // runtime; running them in parallel starves each other and produces timeouts
  // that look like product bugs but are contention. Correctness over speed.
  workers: 1,
  use: { baseURL: 'http://localhost:3000' },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
