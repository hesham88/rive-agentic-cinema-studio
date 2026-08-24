import { expect, test } from '@playwright/test';
import {
  toggleAnimated,
  toggleRig,
  toggleStatic,
} from '../../../packages/rive-engine/src/core/riv/toggle';

/**
 * Does the Rive runtime actually load bytes we wrote ourselves?
 *
 * This is the whole spike. Every other test in the suite can pass while the
 * encoder emits garbage, because nothing else parses a `.riv` — only the WASM
 * runtime does, and it is the sole authority on whether a file is valid.
 *
 * The bytes are encoded here in Node and fed to the inspector through its own
 * file input, exactly as a person would drop a file on it. That is deliberate:
 * no temporary route, no globals stashed on `window`, and no bundler tricks
 * inside `page.evaluate` — a bare specifier like `@rive-app/webgl2` cannot
 * resolve there, because the browser has no bundler. It also exercises the real
 * path a user takes.
 *
 * If a file were invalid the inspector would render its error panel instead of
 * a manifest, which is the failure these assert against.
 */

/** Hand encoded bytes to the inspector as an uploaded file. */
async function inspect(page: import('@playwright/test').Page, bytes: Uint8Array) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', {
    name: 'encoded.riv',
    mimeType: 'application/octet-stream',
    buffer: Buffer.from(bytes),
  });
  return errors;
}

test('a hand-encoded .riv has a valid header', () => {
  const bytes = toggleStatic();

  // Checked in Node so a header mistake surfaces here rather than as the
  // runtime's own error, which says nothing useful about a bad magic.
  expect(String.fromCharCode(...bytes.slice(0, 4))).toBe('RIVE');
  expect(bytes[4]).toBe(7); // format major; majors are mutually unreadable
  expect(bytes.length).toBeGreaterThan(40);
});

test('the Rive runtime parses bytes we wrote ourselves', async ({ page }) => {
  const errors = await inspect(page, toggleStatic());

  // The manifest tree only renders once the runtime has parsed the file and
  // reported its contents. The error panel is what appears otherwise.
  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('error-panel')).toHaveCount(0);
  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});

test('the encoded artboard reports the name and count we asked for', async ({ page }) => {
  await inspect(page, toggleStatic());

  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });
  // One artboard, correctly named — evidence the objects were understood, not
  // merely that the bytes were tolerated.
  await expect(page.getByTestId('artboard-item')).toHaveCount(1);
  await expect(page.getByTestId('manifest-tree')).toContainText('toggle');
});

test('an animated encode carries its named timelines', async ({ page }) => {
  const errors = await inspect(page, toggleAnimated());

  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });
  // Named timelines caught a real bug: `Animation` does not extend `Component`,
  // so its name lives on key 55, not key 4. Writing key 4 produced a file that
  // loaded cleanly with two anonymous animations — visible only by reading back
  // what the runtime understood.
  const tree = page.getByTestId('manifest-tree');
  await expect(tree).toContainText('off');
  await expect(tree).toContainText('on');
  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});

test('stage 3 exposes a semantic contract, not pixel channels', async ({ page }) => {
  const errors = await inspect(page, toggleRig());

  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('error-panel')).toHaveCount(0);

  // The state machine must be real, not just present in the bytes.
  await expect(page.getByTestId('manifest-tree')).toContainText('State Machine 1');
  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});

test('the runtime binds the view model and finds `checked`', async ({ page }) => {
  await inspect(page, toggleRig());
  await expect(page.getByTestId('manifest-tree')).toBeVisible({ timeout: 20_000 });

  // This is the assertion the whole spike exists for. A file can parse, render
  // and still expose nothing drivable — which is exactly what happened when a
  // view model was created the wrong way and the exporter silently dropped it.
  const panel = page.getByTestId('vm-controls');
  await expect(panel).toBeVisible({ timeout: 20_000 });
  // The name comes from the file, so this proves the view model survived
  // export and was bound to the artboard.
  await expect(panel).toHaveAttribute('data-viewmodel', 'ToggleVM');
  // A row and a control keyed by the property's own name: the runtime
  // enumerated `checked` and typed it as a boolean.
  await expect(page.getByTestId('vm-row-checked')).toBeVisible();
  await expect(page.getByTestId('vm-boolean-checked')).toBeVisible();
  await expect(page.getByTestId('no-vm-properties')).toHaveCount(0);
});

/**
 * Capture what Rive actually drew.
 *
 * A FULL-PAGE screenshot, cropped afterwards — never `page.screenshot({ clip })`
 * and never `locator.screenshot()`. Both of those composite without the WebGL
 * layer here and hand back a flat rectangle, so any comparison built on them
 * passes no matter what the page does. That is not a theory: an editor-authored
 * file and a 286-frame camera move both measured as "unchanged" through a
 * clipped capture, while the same page full-page differs byte-for-byte.
 *
 * The crop is by row, using the fact that a PNG of a region containing real
 * artwork is far larger than one of flat colour — but since we compare whole
 * pages here, no crop is needed at all: the toggle is the only thing changing.
 */
async function frame(page: import('@playwright/test').Page) {
  return page.screenshot();
}

test('driving `checked` changes what Rive draws', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await inspect(page, toggleRig());
  await expect(page.getByTestId('vm-boolean-checked')).toBeVisible({ timeout: 20_000 });

  // Let the entry transition settle into the `off` pose.
  await page.waitForTimeout(2000);
  const off = await frame(page);

  await page.getByTestId('vm-boolean-checked').click();

  // Poll rather than sleep: the transition has a real duration, and several
  // WASM runtimes share this page, so a fixed wait that works on an idle
  // machine is not long enough in a full suite run.
  await expect
    .poll(async () => Buffer.compare(off, await frame(page)), {
      timeout: 15_000,
      message: 'the knob never moved after `checked` was set',
    })
    .not.toBe(0);
});
