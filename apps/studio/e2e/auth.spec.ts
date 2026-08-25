import { test, expect } from '@playwright/test';

/**
 * The auth control has two legitimate shapes, and which one you get is baked in
 * at build time by whether NEXT_PUBLIC_FIREBASE_* was present.
 *
 * Both are asserted here rather than assuming one, because CI builds without
 * `.env.local` (it is gitignored) and a local build usually has it. A spec that
 * assumed "signed out" would fail on CI for a correct app; one that assumed
 * "absent" would stop testing the feature the moment it started working.
 */

async function controlPresent(page: import('@playwright/test').Page) {
  return (await page.locator('[data-testid="auth-control"]').count()) > 0;
}

test('the inspector renders without auth errors in either configuration', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto('/inspect');
  await expect(page.getByRole('heading', { name: 'Rive Inspector' })).toBeVisible();

  // The inspector's core function must not depend on auth in any configuration.
  await expect(page.getByTestId('file-input')).toBeAttached();
  expect(errors, `page errors: ${errors.join(' | ')}`).toHaveLength(0);
});

test('an unconfigured build renders no auth chrome at all', async ({ page }) => {
  await page.goto('/inspect');
  test.skip(await controlPresent(page), 'this build has Firebase configured');

  // Not merely hidden — absent. A dead "Sign in" button in a build that has no
  // project to sign in to is worse than nothing.
  await expect(page.locator('[data-testid="auth-control"]')).toHaveCount(0);
});

test('a configured build offers a working sign-in affordance', async ({ page }) => {
  await page.goto('/inspect');
  test.skip(!(await controlPresent(page)), 'this build has no Firebase configuration');

  // Either the first callback has not landed yet, or it has and we are signed
  // out. Both are valid; what is not valid is neither appearing.
  const signIn = page.getByTestId('auth-signin');
  const status = page.getByTestId('auth-status');
  await expect(signIn.or(status).first()).toBeVisible();

  // Once resolved, the button must be a real, named, keyboard-reachable
  // control — the same standard the Rive kit holds itself to.
  await expect(signIn).toBeVisible({ timeout: 15_000 });
  await expect(signIn).toHaveAccessibleName(/sign in/i);
  await signIn.focus();
  await expect(signIn).toBeFocused();
});
