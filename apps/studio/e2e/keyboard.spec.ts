import { test, expect } from '@playwright/test';
import { riv } from './fixtures';

const FILE = riv('paper-plane-interactive.riv');

test('holding a key drives a bound boolean, releasing restores it', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  const hovered = page.getByTestId('vm-boolean-isHovered');
  await expect(hovered).toBeVisible();
  await expect(hovered).not.toBeChecked();

  // 'h' is bound whileHeld -> isHovered. Rive has no keyboard listener; this
  // goes runtime -> view model -> state machine condition.
  await page.locator('body').press('h');
  await expect(hovered).not.toBeChecked(); // press() is down+up, so it restores
});

test('holding an arrow key ramps a bound number over time', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  const boost = page.getByTestId('vm-number-boost');
  await expect(boost).toBeVisible();
  await expect(boost).toHaveValue('0');

  // Hold ArrowUp: ramps at 60/sec, clamped to 100.
  await page.keyboard.down('ArrowUp');
  await page.waitForTimeout(600);
  await page.keyboard.up('ArrowUp');

  const value = Number(await boost.inputValue());
  expect(value).toBeGreaterThan(5);
  expect(value).toBeLessThanOrEqual(100);
});

test('typing in a field does not trigger key bindings', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FILE);

  const boost = page.getByTestId('vm-number-boost');
  await expect(boost).toBeVisible();
  await boost.fill('7');

  // Focus is in a number input - ArrowUp must not ramp the binding.
  // (The browser's own spinner may step the field; the binding must not fire.)
  await boost.focus();
  await page.keyboard.down('ArrowUp');
  await page.waitForTimeout(400);
  await page.keyboard.up('ArrowUp');

  const value = Number(await boost.inputValue());
  expect(value).toBeLessThan(20); // a 400ms ramp would have added ~24
});
