import { expect, test } from '@playwright/test';
import { PROD_URL as LIVE } from './production-url';

/**
 * Checks the DEPLOYED site, not the dev server.
 *
 * A static export can pass every local test and still break in production —
 * a missing asset, a wrong base path, a CDN cache header on a stale `.riv`.
 * This runs against the real URL so those failures surface here rather than
 * in front of someone.
 */

test('the live kit loads all eight Rive controls', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(LIVE, { waitUntil: 'domcontentloaded' });
  await page.locator('#kit').scrollIntoViewIfNeeded();

  await expect(page.locator('#kit canvas')).toHaveCount(8, { timeout: 30_000 });
  const sized = await page
    .locator('#kit canvas')
    .evaluateAll((els) => els.every((el) => (el as HTMLCanvasElement).width > 0));
  expect(sized).toBe(true);

  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});

test('the live kit ships the ui-kit file', async ({ page }) => {
  const res = await page.request.get(`${LIVE}/riv/ui-kit.riv`);
  expect(res.status()).toBe(200);
  const body = await res.body();
  expect(body.length).toBeGreaterThan(4000);
  // The view model must be in the shipped bytes; without it every control
  // renders at its resting pose and nothing responds.
  expect(body.includes(Buffer.from('KitVM'))).toBe(true);
});
