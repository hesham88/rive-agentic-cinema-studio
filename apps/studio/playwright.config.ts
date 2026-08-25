import { defineConfig } from '@playwright/test';

/**
 * Two projects, because the specs answer two different questions.
 *
 * `local` runs against the STATIC EXPORT, not `next dev`. Production is
 * `output: 'export'` served by a CDN, and the two are not the same program: the
 * dev server hydrates differently, and this project has already lost time to a
 * hydration artifact that existed only in dev. Testing the dev server while
 * shipping the export makes that entire class of bug invisible. `serve`
 * defaults to clean URLs, matching `cleanUrls: true` in firebase.json, so
 * `/inspect` resolves the same way here as it does in production.
 *
 * `production` hits the deployed site. It is EXCLUDED from the default run:
 * it needs the network and it reports on whatever is currently deployed, so
 * folding it into the local suite makes a routine test run fail for reasons
 * that have nothing to do with the working tree. Run it deliberately:
 *
 *     npx playwright test --config apps/studio/playwright.config.ts --project production
 */
export default defineConfig({
  testDir: './e2e',
  // Rive loads WASM and paints on a canvas; give it room on a cold start.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // One worker on purpose. Every test mounts a WebGL context and a WASM
  // runtime; running them in parallel starves each other and produces timeouts
  // that look like product bugs but are contention. Correctness over speed.
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'line' : 'list',

  projects: [
    {
      name: 'local',
      testIgnore: /production\.spec\.ts/,
      use: { baseURL: 'http://localhost:4173' },
    },
    {
      name: 'production',
      testMatch: /production\.spec\.ts/,
    },
  ],

  // Serves the built export. `npm run build` is included so the artifact under
  // test is always current — a stale out/ would test the previous commit.
  webServer: {
    command: 'npm run build --workspace apps/studio && npx serve apps/studio/out -l 4173 --no-request-logging',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
    cwd: '../..',
  },
});
