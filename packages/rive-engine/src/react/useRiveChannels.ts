'use client';

import { useCallback, useEffect, useRef } from 'react';
import type { Rive } from '@rive-app/webgl2';
import { springStep, type SpringConfig, type SpringState, SPRING_SNAPPY } from '../core/motion';

/**
 * Drives a Rive widget's view-model numbers from spring physics.
 *
 * The UI kit's `.riv` widgets expose their visual channels — opacity, scale,
 * position, size — as plain view-model numbers, and ship no state-machine
 * transitions. This hook is what makes them move: it holds a spring per
 * channel, integrates them on one shared rAF loop, and writes the result
 * straight onto the bound view model.
 *
 * Why not author the transitions in Rive? Because then every interactive state
 * needs a hand-drawn timeline and a transition, and the motion is frozen at
 * author time. Driving numbers instead means one widget covers hover, press,
 * focus, drag and value changes, and the feel is tuned in code where it can be
 * changed without reopening the editor.
 *
 * The loop stops itself when every spring has settled, so an idle page costs
 * nothing. It restarts on the next `setTarget`.
 */

export type Channels = Record<string, number>;

export interface RiveChannelsOptions {
  /** Per-channel spring override; anything unlisted uses `SPRING_SNAPPY`. */
  springs?: Record<string, SpringConfig>;
  /**
   * Channels written straight through without a spring. Use for values that
   * are already smooth (a drag position following a pointer) — springing them
   * adds lag the user reads as unresponsiveness.
   */
  immediate?: readonly string[];
}

export interface RiveChannelsApi {
  /** Set the resting target for one or more channels. */
  setTarget(next: Partial<Channels>): void;
  /** Jump channels to a value with no motion, e.g. when a widget mounts. */
  snapTo(next: Partial<Channels>): void;
}

export function useRiveChannels(
  rive: Rive | null,
  initial: Channels,
  options: RiveChannelsOptions = {},
): RiveChannelsApi {
  const { springs, immediate } = options;

  // Refs throughout: this loop runs at display rate and must never re-render.
  const state = useRef<Record<string, SpringState>>({});
  const targets = useRef<Channels>({ ...initial });
  const raf = useRef(0);
  const lastTime = useRef(0);
  const immediateSet = useRef<Set<string>>(new Set(immediate ?? []));

  // Seed springs from the initial values on first run only. Re-seeding on every
  // `initial` identity change would yank a widget back mid-interaction, since
  // callers almost always pass an object literal.
  if (Object.keys(state.current).length === 0) {
    for (const [k, v] of Object.entries(initial)) {
      state.current[k] = { value: v, velocity: 0 };
    }
  }

  useEffect(() => {
    immediateSet.current = new Set(immediate ?? []);
  }, [immediate]);

  const write = useCallback(
    (channel: string, value: number) => {
      const vm = rive?.viewModelInstance;
      if (!vm) return;
      try {
        // `number(name)` returns a live property handle, or null when the
        // widget does not declare that channel — which is not an error: a
        // caller may drive a superset of channels across several widgets.
        const prop = vm.number(channel);
        if (prop) prop.value = value;
      } catch {
        /* a channel this widget does not expose */
      }
    },
    [rive],
  );

  const tick = useCallback(() => {
    const now = performance.now();
    const dt = lastTime.current ? (now - lastTime.current) / 1000 : 1 / 60;
    lastTime.current = now;

    let moving = false;
    for (const [channel, target] of Object.entries(targets.current)) {
      const current = state.current[channel] ?? { value: target, velocity: 0 };

      if (immediateSet.current.has(channel)) {
        if (current.value !== target) {
          state.current[channel] = { value: target, velocity: 0 };
          write(channel, target);
        }
        continue;
      }

      const next = springStep(current, target, dt, springs?.[channel] ?? SPRING_SNAPPY);
      state.current[channel] = next;
      if (next.value !== current.value || next.velocity !== 0) {
        write(channel, next.value);
        moving = true;
      }
    }

    if (moving) {
      raf.current = requestAnimationFrame(tick);
    } else {
      raf.current = 0;
      lastTime.current = 0;
    }
  }, [springs, write]);

  const start = useCallback(() => {
    if (raf.current) return;
    lastTime.current = 0;
    raf.current = requestAnimationFrame(tick);
  }, [tick]);

  // Write the resting pose as soon as the instance exists, so a widget is
  // correct on its first painted frame rather than one animation later.
  useEffect(() => {
    if (!rive) return;
    for (const [channel, s] of Object.entries(state.current)) {
      write(channel, s.value);
    }
    // Targets set before the file finished loading have not been drawn yet;
    // kick the loop so they animate in rather than being stranded.
    start();
  }, [rive, write, start]);

  useEffect(() => {
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
      raf.current = 0;
    };
  }, []);

  const setTarget = useCallback(
    (next: Partial<Channels>) => {
      for (const [k, v] of Object.entries(next)) {
        if (v === undefined) continue;
        targets.current[k] = v;
        state.current[k] ??= { value: v, velocity: 0 };
      }
      // Start unconditionally rather than only when a target changed.
      //
      // Under StrictMode React mounts, cleans up, and mounts again. The cleanup
      // cancels the running frame; the second mount then calls setTarget with
      // the SAME values, because refs survive the remount. A `changed` guard
      // would decline to restart the loop and the widget would sit frozen at
      // its resting pose — which is exactly what happened before this comment
      // existed. `start` is idempotent, and the loop exits on its own once
      // everything has settled, so calling it freely costs nothing.
      start();
    },
    [start],
  );

  const snapTo = useCallback(
    (next: Partial<Channels>) => {
      for (const [k, v] of Object.entries(next)) {
        if (v === undefined) continue;
        targets.current[k] = v;
        state.current[k] = { value: v, velocity: 0 };
        write(k, v);
      }
    },
    [write],
  );

  return { setTarget, snapTo };
}
