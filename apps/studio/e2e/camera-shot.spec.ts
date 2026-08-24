import { test } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// Renders the Scene artboard directly with the Rive runtime and captures
// frames across the camera move, so the shot can be reviewed as pictures.
test('capture the camera move', async ({ page }) => {
  const riv = fs.readFileSync('public/riv/scene.riv').toString('base64');
  const outDir = path.join('camera-frames');
  fs.mkdirSync(outDir, { recursive: true });

  await page.goto('/inspect');
  await page.setViewportSize({ width: 1000, height: 620 });

  await page.setContent(`<!doctype html><meta charset=utf-8>
    <style>html,body{margin:0;background:#000}canvas{display:block;width:1000px;height:600px}</style>
    <canvas id="c" width="1000" height="600"></canvas>`);

  await page.addScriptTag({ url: 'https://unpkg.com/@rive-app/canvas@2.40.1' }).catch(() => {});
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

  for (const [label, ms] of [['00-start', 0], ['01-pushin', 1500], ['02-shake', 2300], ['03-follow', 3600], ['04-canted', 4800]] as [string, number][]) {
    await page.waitForTimeout(ms === 0 ? 300 : 900);
    await page.locator('#c').screenshot({ path: path.join(outDir, `${label}.png`) });
  }
  console.log('frames written to', outDir);
});
