import { test } from '@playwright/test';
import fs from 'fs';

test('capture the landing surface', async ({ page }) => {
  fs.mkdirSync('ui-shots', { recursive: true });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: 'ui-shots/01-hero.png' });

  for (const [file, id, wait] of [
    ['02-deck.png', '#deck', 2500],
    ['03-kit.png', '#kit', 3000],
    ['04-pipeline.png', '#pipeline', 900],
    ['05-gallery.png', '#gallery', 2500],
  ] as const) {
    await page.evaluate((sel) => document.querySelector(sel)?.scrollIntoView(), id);
    await page.waitForTimeout(wait);
    await page.screenshot({ path: `ui-shots/${file}` });
  }

  console.log('PAGE ERRORS:', errors.length ? errors.join(' | ') : 'none');
});
