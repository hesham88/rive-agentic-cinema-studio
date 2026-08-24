import { expect, test } from '@playwright/test';

/**
 * Does the hero mark actually move?
 *
 * A logo that renders but sits still looks identical in a screenshot to one
 * that glides, so this compares two full-page captures a second apart. Capture
 * is full-page and never clipped: clipped and element screenshots both
 * composite without the WebGL layer here and return a flat rectangle, so two of
 * them always compare equal.
 */
test('the generated hero mark glides', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');
  await page.waitForTimeout(2500);

  const a = await page.screenshot();
  await page.waitForTimeout(900);
  const b = await page.screenshot();

  expect(Buffer.compare(a, b), 'the mark never moved').not.toBe(0);
});

test('the mark banks toward the pointer', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');
  await page.waitForTimeout(2500);

  // Park the pointer hard left, settle, then hard right. The bank follows the
  // path derivative plus the pointer, so the two states must differ.
  await page.mouse.move(80, 400);
  await page.waitForTimeout(1200);
  const left = await page.screenshot();

  await page.mouse.move(1200, 400);
  await page.waitForTimeout(1200);
  const right = await page.screenshot();

  expect(Buffer.compare(left, right), 'the pointer had no effect').not.toBe(0);
});
