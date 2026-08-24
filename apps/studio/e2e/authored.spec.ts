import { test, expect } from '@playwright/test';

// The asset this test loads was authored by our own pipeline:
// prompt -> Gemini -> vtracer -> rivepath/svgdoc -> MCP createShapes -> export_file
test('the inspector reads a .riv authored by our own pipeline', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', 'public/riv/paper-plane.riv');

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  await expect(page.getByTestId('artboard-item').first()).toBeVisible();
  await expect(page.getByTestId('status')).toHaveText('ready');
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();
});
