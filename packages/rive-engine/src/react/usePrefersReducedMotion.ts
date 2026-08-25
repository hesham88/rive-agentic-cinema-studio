'use client';

import { useEffect, useState } from 'react';

/**
 * Whether the visitor has asked their system to reduce motion.
 *
 * The CSS media query only reaches CSS animations and transitions. Every piece
 * of motion in this project that matters — the hero glide, the camera moves,
 * anything writing into a Rive view model from a rAF loop — is JavaScript, and
 * CSS cannot switch it off. Motion is this project's entire subject, which
 * makes ignoring the preference worse here than it would be on an ordinary
 * site, not better.
 *
 * Starts `false` so the server-rendered markup and the first client render
 * agree; the real value lands in the effect. Erring towards motion for one
 * frame is the right direction — the alternative is a hydration mismatch on
 * every page load.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);

    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    // `addEventListener` is not universal on MediaQueryList; fall back rather
    // than throwing on the browsers that only have the deprecated form.
    if (mq.addEventListener) {
      mq.addEventListener('change', onChange);
      return () => mq.removeEventListener('change', onChange);
    }
    mq.addListener(onChange);
    return () => mq.removeListener(onChange);
  }, []);

  return reduced;
}
