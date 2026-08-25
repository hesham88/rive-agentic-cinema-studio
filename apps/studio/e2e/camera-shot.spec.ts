import { expect, test } from '@playwright/test';
import { artifactDir, rivBytes } from './fixtures';
import fs from 'fs';
import path from 'path';

// Renders the Scene artboard directly with the Rive runtime and captures
// frames across the camera move, so the shot can be reviewed as pictures.
test('capture the camera move', async ({ page }) => {
  const riv = rivBytes('scene.riv').toString('base64');
  const outDir = artifactDir('camera-frames');
  const shots: Buffer[] = [];

  await page.goto('/inspect');
  await page.setViewportSize({ width: 1000, height: 620 });

  await page.setContent(`<!doctype html><meta charset=utf-8>
    <style>html,body{margin:0;background:#000}canvas{display:block;width:1000px;height:600px}</style>
    <canvas id="c" width="1000" height="600"></canvas>`);

  // NOTE: this is the one place the suite reaches the public internet. The
  // failure used to be swallowed with `.catch(() => {})`, which turned "unpkg
  // is unreachable" into a 30-second timeout on the next line with a message
  // about `window.rive` instead. Let it throw and say what actually happened.
  await page.addScriptTag({ url: 'https://unpkg.com/@rive-app/canvas@2.40.1' });
  await page.waitForFunction(() => (window as any).rive !== undefined, { timeout: 30000 });

  await page.evaluate(async (b64) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const w = window as any;
    w.__r = new w.rive.Rive({
      buffer: bin.buffer,
      canvas: document.getElementById('c'),
      artboard: 'Scene',
      animations: 'CameraMove',
      autoplay: true,
      fit: w.rive.Fit.contain,
    });
    await new Promise((res) => w.__r.on('load', res));
  }, riv);

  // Absolute offsets from the moment the animation started.
  //
  // Two bugs lived here. The loop waited a flat 900ms per frame and ignored
  // these numbers entirely; and the numbers themselves ran to 4800ms, while the
  // `CameraMove` LINEAR animation completes in about 750ms and then reports
  // `isPlaying: false`. Four of the five captures were therefore taken after
  // the move had finished, and came out byte-identical.
  //
  // Note this plays the raw animation, not the state machine the landing page
  // drives — `Opening.tsx` runs `State Machine 1`, which is what the 286-frame
  // readout describes. These offsets span the linear animation only.
  const beats: [string, number][] = [
    ['00-start', 60],
    ['01-pushin', 240],
    ['02-shake', 400],
    ['03-follow', 560],
    ['04-canted', 730],
  ];
  const started = Date.now();
  for (const [label, ms] of beats) {
    const remaining = ms - (Date.now() - started);
    if (remaining > 0) await page.waitForTimeout(remaining);
    // FULL-PAGE, not `locator.screenshot()`. An element screenshot does not
    // composite the WebGL layer in this browser, so it returns a flat
    // rectangle: this spec used to emit five "frames" of a 286-frame camera
    // move of which four were byte-identical. A capture that silently produces
    // nothing is worse than no capture, so the frames are checked below.
    await page.screenshot({ path: path.join(outDir, `${label}.png`), fullPage: false });
    shots.push(fs.readFileSync(path.join(outDir, `${label}.png`)));
  }
  // The frames must actually differ. Four of these were once byte-identical —
  // a capture of a 286-frame camera move that showed one frame five times — and
  // nothing said so, because a capture spec asserts nothing by default.
  const distinct = new Set(shots.map((b) => b.toString('base64'))).size;
  expect(distinct, `only ${distinct} distinct frames across the camera move`)
    .toBeGreaterThan(3);

  console.log('frames written to', outDir);
});
