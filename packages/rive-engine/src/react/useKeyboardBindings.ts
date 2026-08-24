'use client';

import { useEffect, useMemo, useRef } from 'react';
import type { ViewModelHandle } from './useViewModelControls';

/**
 * Keyboard-driven interactivity for a Rive artboard.
 *
 * Rive's editor listeners are **pointer, event, or view-model** only — there is
 * no keyboard listener in the format. Keyboard therefore has to be driven from
 * the runtime: the app listens for key events and writes view model properties,
 * which the state machine's conditions already react to.
 *
 * That is why this hook takes `ViewModelHandle`s rather than talking to Rive
 * directly — the view-model layer is the bridge.
 */

export type KeyBinding =
  /** While held, set the property; on release, set it back. */
  | { key: string; property: string; whileHeld: boolean | number; onRelease?: boolean | number }
  /** On keydown, set the property to a fixed value. */
  | { key: string; property: string; setTo: boolean | number | string }
  /** On keydown, fire a trigger property. */
  | { key: string; property: string; fire: true }
  /** While held, ramp a number by `perSecond`, clamped to [min, max]. */
  | { key: string; property: string; rampBy: number; min?: number; max?: number };

export interface KeyboardBindingsOptions {
  /** Element to listen on. Defaults to window. */
  target?: HTMLElement | null;
  /** Ignore key events while focus is in an input/textarea/select. Default true. */
  ignoreWhenTyping?: boolean;
  /** Call preventDefault on bound keys (stops space scrolling the page). Default true. */
  preventDefault?: boolean;
  enabled?: boolean;
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  if (el.isContentEditable) return true;
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
}

/** Normalizes so bindings can be written as "w", "ArrowUp", " " or "Space". */
function normalizeKey(k: string): string {
  if (k === ' ') return 'space';
  return k.toLowerCase();
}

export function useKeyboardBindings(
  handles: ViewModelHandle[],
  bindings: KeyBinding[],
  options: KeyboardBindingsOptions = {},
): void {
  const {
    target,
    ignoreWhenTyping = true,
    preventDefault = true,
    enabled = true,
  } = options;

  const byName = useMemo(() => {
    const m = new Map<string, ViewModelHandle>();
    for (const h of handles) m.set(h.info.name, h);
    return m;
  }, [handles]);

  // Bindings often come from an inline literal; a ref keeps the effect from
  // re-subscribing on every render.
  const bindingsRef = useRef(bindings);
  bindingsRef.current = bindings;
  const handlesRef = useRef(byName);
  handlesRef.current = byName;

  useEffect(() => {
    if (!enabled) return;
    const el: EventTarget = target ?? window;
    const held = new Set<string>();
    let raf = 0;
    let last = performance.now();

    const matching = (key: string) =>
      bindingsRef.current.filter((b) => normalizeKey(b.key) === key);

    const onDown = (ev: Event) => {
      const e = ev as KeyboardEvent;
      if (ignoreWhenTyping && isTypingTarget(e.target)) return;
      const key = normalizeKey(e.key);
      const hits = matching(key);
      if (hits.length === 0) return;
      if (preventDefault) e.preventDefault();
      if (e.repeat) return; // ramps are handled by the rAF loop

      held.add(key);
      for (const b of hits) {
        const h = handlesRef.current.get(b.property);
        if (!h) continue;
        if ('fire' in b) h.fire();
        else if ('setTo' in b) h.set(b.setTo);
        else if ('whileHeld' in b) h.set(b.whileHeld);
      }
    };

    const onUp = (ev: Event) => {
      const e = ev as KeyboardEvent;
      const key = normalizeKey(e.key);
      if (!held.delete(key)) return;
      for (const b of matching(key)) {
        const h = handlesRef.current.get(b.property);
        if (!h) continue;
        if ('whileHeld' in b && b.onRelease !== undefined) h.set(b.onRelease);
      }
    };

    // Blur clears held keys — otherwise alt-tabbing mid-press leaves a property
    // stuck true forever.
    const onBlur = () => {
      for (const key of held) {
        for (const b of matching(key)) {
          const h = handlesRef.current.get(b.property);
          if (h && 'whileHeld' in b && b.onRelease !== undefined) h.set(b.onRelease);
        }
      }
      held.clear();
    };

    const pump = () => {
      const now = performance.now();
      const dt = (now - last) / 1000;
      last = now;
      for (const key of held) {
        for (const b of matching(key)) {
          if (!('rampBy' in b)) continue;
          const h = handlesRef.current.get(b.property);
          if (!h) continue;
          const cur = Number(h.value ?? 0);
          const min = b.min ?? Number.NEGATIVE_INFINITY;
          const max = b.max ?? Number.POSITIVE_INFINITY;
          h.set(Math.min(max, Math.max(min, cur + b.rampBy * dt)));
        }
      }
      raf = requestAnimationFrame(pump);
    };
    raf = requestAnimationFrame(pump);

    el.addEventListener('keydown', onDown);
    el.addEventListener('keyup', onUp);
    window.addEventListener('blur', onBlur);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('keydown', onDown);
      el.removeEventListener('keyup', onUp);
      window.removeEventListener('blur', onBlur);
    };
  }, [target, enabled, ignoreWhenTyping, preventDefault]);
}
