import { test } from '@playwright/test';
import { artifactDir } from './fixtures';
import fs from 'fs';

test('capture the landing surface', async ({ page }) => {
  const shots = artifactDir('ui-shots');
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${shots}/new-01-open.png` });

  for (const [file, id, wait] of [
    ['new-02-process.png', '#pipeline', 900],
    ['new-03-engines.png', '#engines', 900],
    ['new-04-kit.png', '#kit', 3000],
    ['new-05-proof.png', '#proof', 3000],
  ] as const) {
    await page.evaluate((sel) => document.querySelector(sel)?.scrollIntoView(), id);
    await page.waitForTimeout(wait);
    await page.screenshot({ path: `${shots}/${file}` });
  }

  console.log('PAGE ERRORS: ' + (errors.length ? errors.join(' | ') : 'none'));
});
