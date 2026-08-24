'use client';

/**
 * Firebase client — auth for the production environment.
 *
 * Initialised lazily and guarded, because:
 *   * this app prerenders to static HTML, so nothing may touch Firebase during
 *     the build;
 *   * local development runs with no Firebase config at all, and must keep
 *     working — the studio's core function (load a .riv, inspect it, drive it)
 *     needs no account.
 *
 * `isFirebaseConfigured()` is the switch every caller checks first. When it is
 * false the app runs in open local mode rather than erroring.
 */

import type { FirebaseApp } from 'firebase/app';
import type { Auth, User } from 'firebase/auth';

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function isFirebaseConfigured(): boolean {
  return Boolean(config.apiKey && config.projectId && config.authDomain);
}

let appPromise: Promise<FirebaseApp> | null = null;
let authPromise: Promise<Auth> | null = null;

async function getApp(): Promise<FirebaseApp> {
  if (!isFirebaseConfigured()) {
    throw new Error(
      'Firebase is not configured. Set NEXT_PUBLIC_FIREBASE_* in .env.local ' +
        '(see .env.example). Local development does not require it.',
    );
  }
  if (!appPromise) {
    appPromise = (async () => {
      const { getApps, initializeApp } = await import('firebase/app');
      const existing = getApps();
      return existing.length ? existing[0]! : initializeApp(config);
    })();
  }
  return appPromise;
}

export async function getFirebaseAuth(): Promise<Auth> {
  if (!authPromise) {
    authPromise = (async () => {
      const { getAuth, connectAuthEmulator } = await import('firebase/auth');
      const auth = getAuth(await getApp());

      // Point at the local emulator when one is running, so development never
      // touches real accounts.
      if (process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST) {
        connectAuthEmulator(
          auth,
          `http://${process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST}`,
          { disableWarnings: true },
        );
      }
      return auth;
    })();
  }
  return authPromise;
}

export async function signInWithGoogle(): Promise<User> {
  const { GoogleAuthProvider, signInWithPopup } = await import('firebase/auth');
  const auth = await getFirebaseAuth();
  const result = await signInWithPopup(auth, new GoogleAuthProvider());
  return result.user;
}

export async function signOut(): Promise<void> {
  const { signOut: fbSignOut } = await import('firebase/auth');
  await fbSignOut(await getFirebaseAuth());
}

export async function watchAuth(
  onChange: (user: User | null) => void,
): Promise<() => void> {
  if (!isFirebaseConfigured()) {
    onChange(null);
    return () => {};
  }
  const { onAuthStateChanged } = await import('firebase/auth');
  return onAuthStateChanged(await getFirebaseAuth(), onChange);
}
