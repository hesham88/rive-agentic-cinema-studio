import { defineConfig } from 'vitest/config';

/**
 * Unit tests only.
 *
 * Without an explicit exclude, Vitest collects `apps/studio/e2e/*.spec.ts` —
 * Playwright specs that import a browser fixture Vitest cannot provide. They
 * fail at import time, so `vitest run` reports a wall of red while every unit
 * test passes, and stops being usable as a gate. Playwright owns `e2e/`.
 */
export default defineConfig({
  test: {
    include: ['**/*.test.{ts,tsx}'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/e2e/**', '**/.next/**'],
  },
});
