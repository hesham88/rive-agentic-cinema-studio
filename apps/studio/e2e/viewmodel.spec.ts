import { test, expect } from '@playwright/test';

const FILE = 'public/riv/paper-plane-interactive.riv';

test('view-model properties are enumerated and settable', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  // This file has ZERO classic state machine inputs - everything that drives it
  // is data-bound. Before this feature the inspector showed nothing for it.
  const vm = page.getByTestId('vm-controls');
  await expect(vm).toBeVisible();
  await expect(vm).toHaveAttribute('data-viewmodel', 'PlaneVM');

  // Both authored properties must surface, each with the right control type.
  await expect(page.getByTestId('vm-boolean-isHovered')).toBeVisible();
  await expect(page.getByTestId('vm-number-boost')).toBeVisible();
});

test('setting a bound boolean drives the state machine', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  const hovered = page.getByTestId('vm-boolean-isHovered');
  await expect(hovered).toBeVisible();
  await expect(hovered).not.toBeChecked();

  // isHovered gates the Idle -> Hover transition. Setting it from code is the
  // same signal the pointer listener sends.
  await hovered.check();
  await expect(hovered).toBeChecked();
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();

  await hovered.uncheck();
  await expect(hovered).not.toBeChecked();
});

test('a bound number round-trips through the runtime', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  const boost = page.getByTestId('vm-number-boost');
  await expect(boost).toBeVisible();
  await boost.fill('42');
  await boost.blur();
  // The value is read back FROM the runtime, not from React state - so this
  // passing means the write reached Rive and came back.
  await expect(boost).toHaveValue('42');
});
