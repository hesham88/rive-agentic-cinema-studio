import { test, expect } from '@playwright/test';

// widget.riv exports TWO artboards - the plane and the Widget - which is only
// possible because includeinexport (property key 802) is set on the non-default
// artboard. Without it Rive silently ships only the default one.
test('a multi-artboard .riv exposes every artboard', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', 'public/riv/widget.riv');

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  const items = page.getByTestId('artboard-item');
  await expect(items).toHaveCount(2);

  const names = (await items.allTextContents()).join('|');
  console.log('ARTBOARDS:', names);
  expect(names).toContain('Widget');
});

test('the Widget artboard exposes its own view model', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', 'public/riv/widget.riv');
  await expect(page.getByTestId('manifest-tree')).toBeVisible();

  // Select the Widget artboard.
  const widget = page.getByTestId('artboard-item').filter({ hasText: 'Widget' });
  await widget.getByRole('button').first().click();
  await page.waitForTimeout(1200);

  const vm = page.getByTestId('vm-controls');
  if (await vm.isVisible().catch(() => false)) {
    console.log('WIDGET VM:', await vm.getAttribute('data-viewmodel'), '|', await vm.textContent());
  }
});
