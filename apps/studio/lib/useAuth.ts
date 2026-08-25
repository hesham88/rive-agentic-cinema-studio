'use client';

import { useCallback, useEffect, useState } from 'react';
import { isFirebaseConfigured, signInWithGoogle, signOut, watchAuth } from './firebase';
import { authView, type AuthUserLike, type AuthView } from './auth-state';

export interface Auth {
  view: AuthView;
  /** Last failure, shown inline. A popup that is dismissed lands here. */
  error: string | null;
  signIn(): Promise<void>;
  signOut(): Promise<void>;
}

/**
 * Subscribes to Firebase auth and reduces it to a view via `authView`.
 *
 * All the branching lives in `auth-state.ts`, which is pure and unit-tested;
 * this hook only supplies the three facts and forwards the two actions. That
 * split is deliberate — a decision buried in a hook can only be tested through
 * a browser.
 */
export function useAuth(): Auth {
  const configured = isFirebaseConfigured();
  const [resolved, setResolved] = useState(!configured);
  const [user, setUser] = useState<AuthUserLike | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!configured) return;
    let live = true;
    let stop: (() => void) | undefined;

    watchAuth((u) => {
      if (!live) return;
      setUser(u ? { displayName: u.displayName, email: u.email } : null);
      setResolved(true);
    })
      .then((unsub) => {
        // The subscription may resolve after unmount; drop it immediately
        // rather than leaving a listener writing into a dead component.
        if (live) stop = unsub;
        else unsub();
      })
      .catch((e: unknown) => {
        if (!live) return;
        setError(e instanceof Error ? e.message : String(e));
        setResolved(true);
      });

    return () => {
      live = false;
      stop?.();
    };
  }, [configured]);

  const run = useCallback(async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      // Closing the Google popup is a normal thing to do, not a failure worth
      // showing in red.
      if (message.includes('popup-closed-by-user') || message.includes('cancelled-popup')) return;
      setError(message);
    }
  }, []);

  return {
    view: authView({ configured, resolved, user }),
    error,
    signIn: useCallback(() => run(signInWithGoogle), [run]),
    signOut: useCallback(() => run(signOut), [run]),
  };
}
