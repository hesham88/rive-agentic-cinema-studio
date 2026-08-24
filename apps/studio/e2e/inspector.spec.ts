import { test, expect } from '@playwright/test';

const FIXTURE = 'public/riv/sample.riv';
const SECOND = 'public/riv/juice_v7.riv';
const CORRUPT = 'public/riv/corrupt.riv';

test('enumerates artboards from a real .riv file', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FIXTURE);

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  await expect(page.getByTestId('artboard-item').first()).toBeVisible();
  await expect(page.getByTestId('status')).toHaveText('ready');
});

test('a state machine reporting N>0 inputs renders N controls', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FIXTURE);

  // Find a state machine whose own label claims a non-zero input count, so the
  // assertion is anchored to what the manifest reports rather than to a guess.
  const machines = page.getByTestId('state-machine-item');
  await expect(machines.first()).toBeVisible();

  const count = await machines.count();
  let target = null;
  let expected = 0;
  for (let i = 0; i < count; i++) {
    const label = (await machines.nth(i).textContent()) ?? '';
    const m = /\((\d+) inputs?\)/.exec(label);
    if (m && Number(m[1]) > 0) {
      target = machines.nth(i);
      expected = Number(m[1]);
      break;
    }
  }

  expect(target, 'fixture must expose at least one state machine with inputs').not.toBeNull();
  await target!.click();

  await expect(page.getByTestId('rive-stage')).toBeVisible();
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();

  // The real assertion: controls must actually render, one per reported input.
  // `controls.or(noInputs)` would pass on the broken path, which is how this
  // bug shipped as "verified".
  await expect(page.getByTestId('input-controls')).toBeVisible();
  await expect(page.getByTestId('input-controls').locator('li')).toHaveCount(expected);
});

test('loading a second file replaces the first', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', FIXTURE);
  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  const first = await page.getByTestId('manifest-tree').textContent();

  await page.setInputFiles('[data-testid="file-input"]', SECOND);
  await expect
    .poll(async () => page.getByTestId('manifest-tree').textContent(), { timeout: 15_000 })
    .not.toBe(first);
});

test('a corrupt file shows an explicit error, not a blank canvas', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', CORRUPT);

  const err = page.getByTestId('rive-error');
  await expect(err).toBeVisible();
  await expect(err).toHaveAttribute('data-error-kind', /parse|empty|network/);
  await expect(page.getByTestId('rive-error-message')).not.toBeEmpty();
});
