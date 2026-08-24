'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Scroll progress through the document, 0..1, sampled on a frame.
 *
 * Read inside `requestAnimationFrame` rather than in the scroll handler itself:
 * `scrollY` and `getBoundingClientRect` both force layout, and doing that on
 * every scroll event janks the page on a trackpad. One read per painted frame
 * is exactly as much resolution as a playhead can show.
 */
export function useScrollProgress(): number {
  const [progress, setProgress] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    const measure = () => {
      raf.current = 0;
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 0);
    };
    const onScroll = () => {
      if (!raf.current) raf.current = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, []);

  return progress;
}

/**
 * Which of `ids` is currently the active section.
 *
 * Resolves by "the last one whose top has passed the trigger line" rather than
 * by IntersectionObserver ratios: a short section and a tall one produce wildly
 * different ratios, so a ratio-based winner flickers between them. A single
 * trigger line is stable and matches how a reader decides what they are looking
 * at.
 */
export function useActiveSection(ids: readonly string[]): number {
  const [active, setActive] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    const measure = () => {
      raf.current = 0;
      const line = window.innerHeight * 0.35;
      let current = 0;
      ids.forEach((id, i) => {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= line) current = i;
      });
      setActive(current);
    };
    const onScroll = () => {
      if (!raf.current) raf.current = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [ids]);

  return active;
}

/**
 * Reveal an element once, when it first enters view.
 *
 * `once` matters: elements that re-animate every time you scroll past them are
 * the clearest tell of a template. `delayMs` staggers siblings — 70ms is about
 * four frames at 60fps, which is the offset a hand-animated group uses for
 * overlapping action.
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

    // Progressive enhancement must never hide content on failure.
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
      { rootMargin: '0px 0px -10% 0px', threshold: 0.08 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [delayMs]);

  return ref;
}
