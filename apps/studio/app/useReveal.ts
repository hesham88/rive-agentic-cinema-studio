'use client';

import { useEffect, useRef } from 'react';

/**
 * Reveals an element once, when it first enters the viewport.
 *
 * `once` matters: elements that re-animate every time you scroll past them are
 * the clearest tell of a template. It also unobserves itself, so a long page
 * does not keep dozens of live observers around.
 *
 * If IntersectionObserver is missing (or motion is reduced, which the
 * stylesheet already handles), the element is shown immediately rather than
 * left invisible — a progressive enhancement must never hide content on
 * failure.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(delayMs = 0) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const show = () => {
      el.style.transitionDelay = `${delayMs}ms`;
      el.dataset.shown = 'true';
    };

    if (typeof IntersectionObserver === 'undefined') {
      show();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            show();
            io.unobserve(entry.target);
          }
        }
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.1 },
    );

    io.observe(el);
    return () => io.disconnect();
  }, [delayMs]);

  return ref;
}
