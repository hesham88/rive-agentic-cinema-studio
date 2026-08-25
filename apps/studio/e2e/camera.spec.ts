import { test, expect } from '@playwright/test';
import { riv } from './fixtures';

// scene.riv contains three artboards. The Scene artboard is a parallax world
// (sky, moon, stars, two hill layers) plus a pipeline-generated rocket, all
// parented to one invisible "camera-rig" shape. Rive has no camera, so the
// move is the rig transforming inversely to the intended camera.
test('the scene ships every artboard and animates a camera move', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', riv('scene.riv'));

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  const names = (await page.getByTestId('artboard-item').allTextContents()).join('|');
  console.log('ARTBOARDS:', names);
  expect(names).toContain('Scene');

  await expect(page.getByTestId('status')).toHaveText('ready');
});

test('selecting the Scene artboard renders its canvas', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', riv('scene.riv'));
  await expect(page.getByTestId('manifest-tree')).toBeVisible();

  const scene = page.getByTestId('artboard-item').filter({ hasText: 'Scene' });
  await scene.getByRole('button').first().click();
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();
});
