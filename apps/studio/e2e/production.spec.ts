import { test, expect } from '@playwright/test';
import { PROD_URL as PROD } from './production-url';

// A 200 from curl proves the CDN serves bytes. It does not prove the WASM
// runtime boots, the canvas paints, or a .riv authored by our pipeline loads.
test('the deployed studio loads and renders a pipeline-authored .riv', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(`${PROD}/inspect`, { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Rive Inspector' })).toBeVisible();

  // Load the widget straight from the CDN, as a real visitor's browser would.
  const res = await page.request.get(`${PROD}/riv/widget.riv`);
  expect(res.status()).toBe(200);
  const buf = await res.body();
  // The MAGIC, not an exact byte count. Pinning the length made a re-export of
  // widget.riv fail a test that is not about file size; the magic proves the
  // CDN served a real Rive binary rather than an error page, which is the
  // thing actually under test here.
  expect(buf.subarray(0, 4).toString()).toBe('RIVE');
  expect(buf.length).toBeGreaterThan(1024);

  await page.setInputFiles('[data-testid="file-input"]', {
    name: 'widget.riv',
    mimeType: 'application/octet-stream',
    buffer: buf,
  });

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  await expect(page.getByTestId('artboard-item')).toHaveCount(2);
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();

  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});
