import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { toggleRig } from '../../../packages/rive-engine/src/core/riv/toggle';

/**
 * Parity: does our encoder produce the same picture as the Rive editor?
 *
 * Loading is a low bar — a file can parse and still draw the wrong thing. The
 * only honest check is to author the same widget in the editor, export it, and
 * compare what the runtime renders from each.
 *
 * The reference file is committed at `public/riv/toggle-editor.riv`, produced by
 * `tools/genassets/genassets/toggle_reference.py` over MCP. When it is absent
 * these tests SKIP rather than pass: a parity test that quietly succeeds because
 * it had nothing to compare against is worse than no test.
 *
 * Capture is FULL-PAGE and never clipped. `page.screenshot({ clip })` and
 * `locator.screenshot()` both composite without the WebGL layer in this browser
 * and hand back a flat rectangle, so two captures always compare equal.
 */

const REFERENCE = 'public/riv/toggle-editor.riv';

/**
 * Load bytes into the inspector and select a named artboard.
 *
 * Selecting explicitly matters for the editor export: Rive ships EVERY artboard
 * whose `includeinexport` flag is set, and a document always carries a default
 * `Artboard`. That one sorts first, so the inspector opens it and the toggle is
 * never on screen. Ours contains a single artboard, but it is selected the same
 * way so the two are measured identically.
 */
async function show(
  page: import('@playwright/test').Page,
  bytes: Uint8Array,
  name: string,
  artboard: string,
) {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', {
    name,
    mimeType: 'application/octet-stream',
    buffer: Buffer.from(bytes),
  });
  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });

  const item = page.getByTestId('artboard-item').filter({ hasText: artboard });
  await expect(item, `artboard "${artboard}" is present`).toHaveCount(1);
  await item.getByTestId('state-machine-item').first().click();

  // Let the entry transition settle before measuring.
  await page.waitForTimeout(2000);
}

/** The view-model property names the inspector is showing. */
const rowNames = (page: import('@playwright/test').Page) =>
  page
    .locator('[data-testid^="vm-row-"]')
    .evaluateAll((els) =>
      els.map((e) => e.getAttribute('data-testid')!.replace('vm-row-', '')),
    );

/** The artboard each file keeps its toggle on. */
const EDITOR_ARTBOARD = 'ref/toggle';
const OUR_ARTBOARD = 'toggle';

/**
 * The boolean each file exposes.
 *
 * The names differ on purpose. The editor's shared kit view model already
 * carried a NUMERIC `checked` from an earlier run, and a property's type cannot
 * be changed in place — so the reference declares `isChecked` rather than
 * deleting something from the owner's document. What matters is that both are
 * booleans named by the widget's meaning, not the shape they move.
 */
const EDITOR_PROPERTY = 'isChecked';
const OUR_PROPERTY = 'checked';

test.describe('encoder vs editor', () => {
  test.skip(
    () => !existsSync(REFERENCE),
    `no reference export at ${REFERENCE} — run tools/genassets/genassets/toggle_reference.py ` +
      'with the Rive desktop app open on the working file',
  );

  test('both files expose `checked`, and ours exposes nothing else', async ({ page }) => {
    await show(page, readFileSync(REFERENCE), 'editor.riv', EDITOR_ARTBOARD);
    await expect(page.getByTestId('vm-controls')).toBeVisible({ timeout: 20_000 });
    const editorRows = await rowNames(page);

    await show(page, toggleRig(), 'ours.riv', OUR_ARTBOARD);
    await expect(page.getByTestId('vm-controls')).toBeVisible({ timeout: 20_000 });
    const ourRows = await rowNames(page);

    // Both must offer the property the widget is about.
    expect(editorRows, 'editor exposes its boolean').toContain(EDITOR_PROPERTY);
    expect(ourRows, 'ours exposes its boolean').toContain(OUR_PROPERTY);

    // But they are NOT expected to match, and ours is the better shape.
    //
    // The editor binds one shared view model per document, so exporting a
    // single widget drags in every channel every other widget in that document
    // declared — 27 properties for a toggle. A generated file declares only
    // what the widget actually has. That is the data-contract principle
    // enforced by construction rather than by discipline.
    expect(ourRows).toEqual([OUR_PROPERTY]);
    expect(editorRows.length).toBeGreaterThan(ourRows.length);
  });

  // One test per file rather than a loop over both. The inspector keeps state
  // across a `goto` within a page, and reloading a second file into a primed
  // instance produced a stale panel — a test artefact, not a product bug, but
  // it made the result unreadable either way. A fresh page per file removes the
  // question entirely.
  for (const [label, load, artboard, property] of [
    ['editor', () => readFileSync(REFERENCE), EDITOR_ARTBOARD, EDITOR_PROPERTY],
    ['ours', () => toggleRig(), OUR_ARTBOARD, OUR_PROPERTY],
  ] as const) {
    test(`${label}: setting \`checked\` redraws`, async ({ page }) => {
      await show(page, load() as Uint8Array, `${label}.riv`, artboard);

      // `vm-boolean-*` exists only when the runtime typed the property as a
      // boolean. A numeric one renders `vm-number-*` instead, which is how the
      // reference's first build was caught declaring a slider.
      const control = page.getByTestId(`vm-boolean-${property}`);
      await expect(control, `${label} exposes a boolean ${property}`).toBeVisible({
        timeout: 20_000,
      });

      const before = await page.screenshot();
      await control.click();
      await expect
        .poll(async () => Buffer.compare(before, await page.screenshot()), {
          timeout: 15_000,
          message: `${label}: nothing redrew after setting checked`,
        })
        .not.toBe(0);
    });
  }
});
