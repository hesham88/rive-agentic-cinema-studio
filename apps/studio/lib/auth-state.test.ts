import { describe, it, expect } from 'vitest';
import { authView, type AuthInputs } from './auth-state';

const inputs = (p: Partial<AuthInputs> = {}): AuthInputs => ({
  configured: true,
  resolved: true,
  user: null,
  ...p,
});

describe('authView', () => {
  it('reports unavailable when Firebase is not configured', () => {
    // Local development runs with no Firebase project at all and must keep
    // working. "Unavailable" is not an error state; it is open local mode.
    expect(authView(inputs({ configured: false }))).toEqual({ kind: 'unavailable' });
  });

  it('stays unavailable even if a stale user is somehow present', () => {
    // Guards against showing a signed-in chrome in an environment that cannot
    // actually verify anyone.
    expect(
      authView(inputs({ configured: false, user: { displayName: 'X', email: 'x@y.z' } })),
    ).toEqual({ kind: 'unavailable' });
  });

  it('reports loading before the first auth callback arrives', () => {
    // Firebase resolves the current user asynchronously. Rendering "signed out"
    // during that gap makes the button flicker to "Sign in" for a returning
    // user, which reads as having been logged out.
    expect(authView(inputs({ resolved: false }))).toEqual({ kind: 'loading' });
  });

  it('reports signed out once resolved with no user', () => {
    expect(authView(inputs({ user: null }))).toEqual({ kind: 'signed-out' });
  });

  it('labels a signed-in user by display name', () => {
    expect(authView(inputs({ user: { displayName: 'Ada Lovelace', email: 'ada@x.dev' } })))
      .toEqual({ kind: 'signed-in', label: 'Ada Lovelace' });
  });

  it('falls back to the email when there is no display name', () => {
    expect(authView(inputs({ user: { displayName: null, email: 'ada@x.dev' } })))
      .toEqual({ kind: 'signed-in', label: 'ada@x.dev' });
  });

  it('falls back to a generic label when the account has neither', () => {
    // An anonymous or phone-only account has neither field. Rendering "null"
    // into the header is the failure this prevents.
    expect(authView(inputs({ user: { displayName: null, email: null } })))
      .toEqual({ kind: 'signed-in', label: 'Signed in' });
  });
});
