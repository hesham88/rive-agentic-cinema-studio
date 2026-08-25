/**
 * What the auth chrome should show, derived from the three facts that decide it.
 *
 * Pure and free of both React and Firebase, so the decision can be unit-tested
 * without a browser or a project — the same reason `rive-engine/core` imports
 * nothing. The Firebase-shaped parts live in `firebase.ts`; this file only
 * decides what the result means.
 */

/** The subset of a Firebase `User` this decision needs. */
export interface AuthUserLike {
  displayName: string | null;
  email: string | null;
}

export interface AuthInputs {
  /** Whether NEXT_PUBLIC_FIREBASE_* is present at all. */
  configured: boolean;
  /** Whether the first `onAuthStateChanged` callback has arrived. */
  resolved: boolean;
  user: AuthUserLike | null;
}

export type AuthView =
  /** No Firebase project configured. Open local mode — not an error. */
  | { kind: 'unavailable' }
  /** Configured, but the current user is not yet known. */
  | { kind: 'loading' }
  | { kind: 'signed-out' }
  | { kind: 'signed-in'; label: string };

export function authView({ configured, resolved, user }: AuthInputs): AuthView {
  // Checked first and unconditionally: without a project there is nothing that
  // could have verified a user, so any user object present is stale.
  if (!configured) return { kind: 'unavailable' };
  if (!resolved) return { kind: 'loading' };
  if (!user) return { kind: 'signed-out' };
  return { kind: 'signed-in', label: user.displayName || user.email || 'Signed in' };
}
