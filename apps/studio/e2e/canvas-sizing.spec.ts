import { expect, test } from '@playwright/test';

/**
 * Every Rive canvas must have a non-zero drawing buffer.
 *
 * A canvas has two sizes: the CSS box the browser lays out, and the
 * `width`/`height` attributes backing the WebGL buffer. When they fall out of
 * step the canvas is left at the HTML default of 300x150 and draws nothing —
 * silently. The `.riv` loads, the state machine advances, inputs respond, and
 * the only missing thing is pixels. See useCanvasResync.
 *
 * `kit.spec.ts` already asserts this for the eight kit controls. Nothing
 * guarded the hero, and a hook added in the wrong ORDER — pausing the runtime
 * before it had sized its surface — put the hero canvas straight back to
 * 300x150 with every other test still green. Hence this.
 */
test('no Rive canvas is left at the unsized HTML default', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/');

  // Scroll the whole page so lazily-revealed sections mount and lay out.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 600) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  const measure = () =>
    page.locator('canvas').evaluateAll((els) =>
      els.map((el) => {
        const c = el as HTMLCanvasElement;
        return { w: c.width, h: c.height };
      }),
    );

  expect((await measure()).length, 'no canvases found — the page did not render')
    .toBeGreaterThan(0);

  // POLLED, not a fixed sleep. Sizing happens after the runtime boots, and how
  // long that takes depends on machine load — a flat wait made this test report
  // a product bug whenever the suite was busy.
  await expect
    .poll(
      async () =>
        (await measure()).filter((s) => (s.w === 300 && s.h === 150) || s.w === 0 || s.h === 0)
          .length,
      { timeout: 40_000, message: 'canvases were left with an unsized drawing buffer' },
    )
    .toBe(0);
});

test('the hero canvas is sized to its container, not the default', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/');

  const hero = page.locator('#open canvas').first();
  await expect(hero).toBeAttached();

  // Comfortably larger than 300x150 in both axes, so this cannot pass on the
  // default by coincidence.
  await expect
    .poll(async () => hero.evaluate((el) => (el as HTMLCanvasElement).width), {
      timeout: 40_000,
      message: 'the hero canvas never got a real drawing buffer',
    })
    .toBeGreaterThan(400);

  const h = await hero.evaluate((el) => (el as HTMLCanvasElement).height);
  expect(h).toBeGreaterThan(200);
});
