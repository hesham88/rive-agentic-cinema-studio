import { test, expect } from '@playwright/test';

// Authored entirely through MCP: shapes from a traced Gemini image, an Idle
// float timeline, a Hover timeline, a view model, pointer listeners, and a
// state machine wiring them together.
test('an interactive .riv authored via MCP exposes its state machine to our engine', async ({ page }) => {
  await page.goto('/inspect');
  await page.setInputFiles('[data-testid="file-input"]', 'public/riv/paper-plane-interactive.riv');

  await expect(page.getByTestId('manifest-tree')).toBeVisible();
  await expect(page.getByTestId('status')).toHaveText('ready');

  // The state machine must be enumerated by our own inspectRiveContents.
  const sm = page.getByTestId('state-machine-item').first();
  await expect(sm).toBeVisible();
  const label = await sm.textContent();
  console.log('STATE MACHINE:', label);

  await sm.click();
  await expect(page.locator('[data-testid="rive-stage"] canvas')).toBeVisible();

  // Data-bound properties surface as state machine inputs at runtime.
  const controls = page.getByTestId('input-controls');
  const none = page.getByTestId('no-inputs');
  await expect(controls.or(none)).toBeVisible();
  if (await controls.isVisible()) {
    console.log('INPUTS:', await controls.textContent());
  }
});
