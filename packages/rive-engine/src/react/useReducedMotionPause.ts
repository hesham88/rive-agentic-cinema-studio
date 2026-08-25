'use client';

import { useEffect, useRef } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

/** The slice of the runtime this needs. Keeps the hook testable and loose. */
interface Pausable {
  pause?: () => void;
  play?: () => void;
}

/**
 * Pause an AMBIENT Rive graphic when the visitor has asked for reduced motion.
 *
 * For decorative playback only — a hero scene, a showcase tile, anything that
 * animates because the page is open rather than because someone acted. The
 * artwork stays on screen at its current frame; only the movement stops.
 *
 * Do NOT use this on an interactive control. A button that cannot animate its
 * own press still has to acknowledge the press, and freezing it would remove
 * feedback rather than motion. Reduced motion means less movement, not a dead
 * interface.
 */
export function useReducedMotionPause(rive: Pausable | null): boolean {
  const reduced = usePrefersReducedMotion();
  // Only ever resume something this hook itself paused.
  const paused = useRef(false);

  useEffect(() => {
    if (!rive) return;

    if (reduced) {
      rive.pause?.();
      paused.current = true;
      return;
    }

    // Deliberately NOT an unconditional `play()`. Calling it on an instance
    // that is already running restarts playback and can pull an artboard off
    // its state machine onto a plain animation — which showed up as the hero
    // going still under the default preference, the opposite of the intent.
    if (paused.current) {
      rive.play?.();
      paused.current = false;
    }
  }, [rive, reduced]);

  return reduced;
}
