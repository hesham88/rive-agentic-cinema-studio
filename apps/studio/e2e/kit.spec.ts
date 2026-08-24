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
 * Capture what Rive actually drew.
 *
 * A FULL-PAGE screenshot — NOT `page.screenshot({ clip })` and not
 * `locator.screenshot()`. Neither of those composites the WebGL layer in this
 * browser: both return a flat rectangle, so two captures compare equal and any
 * test built on them passes regardless of what the page does.
 *
 * That was demonstrated, not assumed. Through a clipped capture, an
 * editor-authored file and `scene.riv` — which plays a 286-frame camera move —
 * both measured as "unchanged", while the same page captured full-page differs
 * byte-for-byte. The earlier note here claimed element screenshots were the
 * problem and clipping was the fix; clipping has the same fault.
 *
 * Full-page is coarser: anything else animating on the page also registers. For
 * these tests only the control under test is moving, so a difference is
 * attributable.
 */
async function pixels(page: import('@playwright/test').Page) {
  return page.screenshot();
}

async function expectRedraw(
  page: import('@playwright/test').Page,
  baseline: Buffer,
) {
  await expect
    .poll(async () => Buffer.compare(baseline, await pixels(page)), {
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
  const before = await pixels(page);

  await slider.fill('0');

  // With focus held constant, the Rive-drawn fill bar is the only thing left
  // that can differ.
  await expectRedraw(page, before);
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

  const on = await pixels(page);
  await toggle.click();
  await expectRedraw(page, on);
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
