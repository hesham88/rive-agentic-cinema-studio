import { expect, test } from '@playwright/test';

/**
 * The kit's claim is that these controls are Rive artboards driven by real view
 * model numbers — not CSS with a canvas next to it. A test that only checked
 * "the slider moved" would pass against a pure-CSS slider, so it would prove
 * nothing.
 *
 * These assertions therefore reach past the DOM and read the numbers the page
 * actually wrote into Rive, by counting canvases and by driving a control and
 * observing that the *rendered pixels* changed.
 */

test('every control in the kit is a Rive canvas', async ({ page }) => {
  await page.goto('/');
  const kit = page.locator('#kit');
  await kit.scrollIntoViewIfNeeded();

  // Tabs, field, two sliders, toggle, select, progress, button = 8 artboards.
  await expect(kit.locator('canvas')).toHaveCount(8, { timeout: 25_000 });

  // Each canvas must have actually been sized by the runtime; a Rive canvas
  // that failed to load stays 0x0 and would still satisfy a count assertion.
  const sizes = await kit.locator('canvas').evaluateAll((els) =>
    els.map((el) => {
      const c = el as HTMLCanvasElement;
      return { w: c.width, h: c.height };
    }),
  );
  expect(sizes.length).toBe(8);
  for (const s of sizes) {
    expect(s.w).toBeGreaterThan(0);
    expect(s.h).toBeGreaterThan(0);
  }
});

test('the controls are real focusable elements, not canvas hit targets', async ({ page }) => {
  await page.goto('/');
  await page.locator('#kit').scrollIntoViewIfNeeded();

  // Keyboard operation is the point of putting native elements underneath.
  const slider = page.getByLabel('Grain');
  await expect(slider).toHaveValue('42');
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveValue('43');

  const toggle = page.getByRole('switch', { name: 'Motion blur' });
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  await toggle.press('Enter');
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
});

/**
 * Capture the pixels of one element.
 *
 * Deliberately NOT `locator.screenshot()`: an element screenshot of a WebGL
 * canvas comes back blank in this browser, because the drawing buffer is not
 * preserved between frames. Two blank captures compare equal, so a test built
 * on them passes no matter what the page does. Clipping a page screenshot goes
 * through the compositor instead and captures what is actually on screen.
 */
async function pixels(page: import('@playwright/test').Page, locator: import('@playwright/test').Locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error('element has no box to capture');
  return page.screenshot({ clip: box });
}

/**
 * Wait until what Rive draws inside `locator` differs from `baseline`.
 *
 * Polling rather than sleeping a fixed time: several WASM runtimes and WebGL
 * contexts share this page, and how long the first frame after a change takes
 * depends on what else is warming up. A fixed wait that is long enough on an
 * idle page is not long enough in a full suite run, which turns a correct
 * feature into a flaky test.
 */
async function expectRedraw(
  page: import('@playwright/test').Page,
  locator: import('@playwright/test').Locator,
  baseline: Buffer,
) {
  await expect
    .poll(async () => Buffer.compare(baseline, await pixels(page, locator)), {
      timeout: 15_000,
      message: 'Rive never redrew the control after it was driven',
    })
    .not.toBe(0);
}

test('driving a control changes what Rive draws', async ({ page }) => {
  await page.goto('/');
  await page.locator('#kit').scrollIntoViewIfNeeded();

  const slider = page.getByLabel('Bloom');
  const stage = slider.locator('xpath=..');
  await expect(stage).toBeVisible();
  await page.waitForTimeout(1500);

  // Focus FIRST, and sample after: a focused element draws an outline, and
  // comparing an unfocused frame with a focused one would pass on the outline
  // alone — proving nothing about Rive.
  await slider.focus();
  await page.waitForTimeout(400);
  const before = await pixels(page, stage);

  await slider.fill('0');

  // With focus held constant, the Rive-drawn fill bar is the only thing left
  // that can differ.
  await expectRedraw(page, stage, before);
});

test('the kit writes real values into the Rive view model', async ({ page }) => {
  await page.goto('/');
  await page.locator('#kit').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);

  // The toggle's knob position is a number the page writes into KitVM. It
  // cannot be read back out of the canvas, so assert on the consequence: the
  // knob must be drawn somewhere different once the switch flips.
  const toggle = page.getByRole('switch', { name: 'Motion blur' });
  await expect(toggle).toBeVisible();

  const on = await pixels(page, toggle);
  await toggle.click();
  await expectRedraw(page, toggle, on);
});

test('the render button reports its own state', async ({ page }) => {
  await page.goto('/');
  await page.locator('#kit').scrollIntoViewIfNeeded();

  const button = page.getByTestId('kit-render');
  await expect(button).toContainText('Render scene');
  await button.click();
  await expect(button).toContainText('Rendering');
  await expect(button).toBeDisabled();
});
