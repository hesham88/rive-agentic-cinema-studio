import { test, expect } from '@playwright/test';

/**
 * `prefers-reduced-motion` on a site whose whole subject is motion.
 *
 * globals.css already neutralises CSS animations and transitions, but the
 * ambient graphic is a WebGL scene driven by a Rive state machine with a
 * rAF-driven frame readout beside it. CSS reaches neither, so a visitor who had
 * asked their system to stop animation got the full camera move regardless.
 *
 * Asserted on the DOM readout rather than on pixels: it runs off the same
 * preference as the ambient scene, and unlike a screenshot diff it does not
 * also register the kit controls, which stay live on purpose — a paused canvas
 * cannot redraw a control's new value, so freezing those would remove feedback
 * rather than motion.
 */

/**
 * Wait until the Rive runtime has actually booted.
 *
 * Under reduced motion the readout never advances BY DESIGN, so "it did not
 * move" is also what a page that never loaded looks like. The canvas being
 * sized past the 300x150 HTML default is independent proof that the runtime
 * came up, which is what makes the negative assertion mean anything.
 *
 * This also fixes a real flake: with fixed waits, a slower full-suite run
 * sampled the readout before the scene had booted and the CONTROL failed.
 */
async function waitForSceneBoot(page: import('@playwright/test').Page) {
  const canvas = page.locator('#open canvas').first();
  await expect(canvas).toBeAttached();
  await expect
    .poll(
      async () => canvas.evaluate((el) => (el as HTMLCanvasElement).width),
      { timeout: 30_000, message: 'the hero canvas never got a real drawing buffer' },
    )
    .toBeGreaterThan(400);
}

test('the ambient camera move stops under reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await waitForSceneBoot(page);

  const readout = page.getByTestId('camera-frame');
  const first = await readout.textContent();
  await page.waitForTimeout(2000);
  const second = await readout.textContent();

  expect(
    second,
    'the camera readout kept advancing under prefers-reduced-motion: reduce',
  ).toBe(first);
});

test('the ambient camera move runs when no preference is set', async ({ page }) => {
  // The control. Without it the test above would also pass on a page whose
  // readout never rendered at all.
  //
  // This also inherits what `hero-motion.spec.ts` was supposed to cover. That
  // spec asserted "the generated hero mark glides" against a HeroMark component
  // that is deliberately absent from the page (see Opening.tsx) — it was
  // comparing two full-page screenshots and passing on whatever else happened
  // to repaint. It went red the moment the ambient scene settled earlier, which
  // is the tell for a test that was never measuring its stated subject.
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  await waitForSceneBoot(page);

  const readout = page.getByTestId('camera-frame');
  const first = await readout.textContent();

  // Polled, not a fixed pair of samples: the assertion is "it advances", and
  // how quickly it gets going depends on how loaded the machine is.
  await expect
    .poll(async () => readout.textContent(), {
      timeout: 20_000,
      message: 'the camera readout never advanced even with motion allowed',
    })
    .not.toBe(first);
});
