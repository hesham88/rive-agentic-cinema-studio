import { expect, test } from '@playwright/test';

/**
 * The control deck's whole claim is that it reads inputs off the running state
 * machine rather than showing hardcoded buttons. A test that only checked "some
 * controls are visible" would pass against a hardcoded panel, so it would prove
 * nothing.
 *
 * These assertions are built to fail if the deck ever stops reading the file:
 * the rendered control count is compared against the count the deck itself
 * reports, and switching rigs must produce a *different* set of input names.
 */

const CONTROL = '[data-testid^="deck-boolean-"], [data-testid^="deck-number-"], [data-testid^="deck-trigger-"]';

async function inputNames(page: import('@playwright/test').Page) {
  return page.$$eval(CONTROL, (els) =>
    els
      .map((el) => el.getAttribute('data-testid') ?? '')
      .map((id) => id.replace(/^deck-(boolean|number|trigger)-/, ''))
      .sort(),
  );
}

test('the deck builds one control per declared input', async ({ page }) => {
  await page.goto('/');
  const deck = page.locator('#deck');
  await deck.scrollIntoViewIfNeeded();

  // Wait for the machine to instance — before that the deck honestly says so.
  await expect(deck.getByText(/found/)).toBeVisible();
  await expect(page.getByTestId('deck-empty')).toHaveCount(0, { timeout: 20_000 });

  const reported = Number(
    (await deck.getByText(/\d+ found/).innerText()).replace(/\D/g, ''),
  );
  expect(reported).toBeGreaterThan(0);

  // The headline assertion: what the deck says it found must equal what it drew.
  await expect(page.locator(CONTROL)).toHaveCount(reported);
});

test('switching rigs rebuilds the deck from the new file', async ({ page }) => {
  await page.goto('/');
  await page.locator('#deck').scrollIntoViewIfNeeded();
  await expect(page.getByTestId('deck-empty')).toHaveCount(0, { timeout: 20_000 });

  const first = await inputNames(page);
  expect(first.length).toBeGreaterThan(0);

  await page.getByRole('tab', { name: 'Jeep', exact: true }).click();
  await expect(page.getByTestId('deck-empty')).toHaveCount(0, { timeout: 20_000 });

  const second = await inputNames(page);
  expect(second.length).toBeGreaterThan(0);

  // Two different files, two different interfaces. If these ever match, the
  // deck has stopped reading the file it was pointed at.
  expect(second).not.toEqual(first);
});

test('firing a trigger is recorded by the deck', async ({ page }) => {
  await page.goto('/');
  await page.locator('#deck').scrollIntoViewIfNeeded();
  await expect(page.getByTestId('deck-empty')).toHaveCount(0, { timeout: 20_000 });

  const signals = page.getByText(/signals? sent this session/);
  await expect(signals).toContainText('0 signals');

  const trigger = page.locator('[data-testid^="deck-trigger-"]').first();
  const toggle = page.locator('[data-testid^="deck-boolean-"]').first();

  // Whichever kind this rig declares — the point is that a control reaches the
  // runtime and the deck counts it.
  if (await trigger.count()) {
    await trigger.click();
  } else {
    await toggle.click();
  }

  await expect(signals).toContainText('1 signal');
});
