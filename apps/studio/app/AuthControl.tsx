'use client';

import { useAuth } from '../lib/useAuth';

/**
 * The sign-in control.
 *
 * Renders NOTHING when Firebase is unconfigured. Local development runs without
 * a project on purpose — a contributor should be able to clone and inspect a
 * `.riv` without provisioning anything — so an auth control that rendered a
 * dead button there would be worse than no control at all.
 */
export function AuthControl() {
  const { view, error, signIn, signOut } = useAuth();

  if (view.kind === 'unavailable') return null;

  return (
    <div data-testid="auth-control" className="flex items-center gap-3">
      {error ? (
        <span role="alert" className="text-[11px] text-red-400">
          {error}
        </span>
      ) : null}

      {view.kind === 'loading' ? (
        <span data-testid="auth-status" className="text-[12px] text-dim" aria-live="polite">
          Checking sign-in…
        </span>
      ) : view.kind === 'signed-in' ? (
        <>
          <span data-testid="auth-user" className="text-[12px] text-dim">
            {view.label}
          </span>
          <button type="button" onClick={signOut} className="btn btn-ghost !py-1.5 !text-[12px]">
            Sign out
          </button>
        </>
      ) : (
        <button
          type="button"
          data-testid="auth-signin"
          onClick={signIn}
          className="btn btn-ghost !py-1.5 !text-[12px]"
        >
          Sign in
        </button>
      )}
    </div>
  );
}
