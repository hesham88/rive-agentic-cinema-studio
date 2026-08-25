'use client';

import { useEffect, useRef, useState } from 'react';
import type { Rive } from '@rive-app/webgl2';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

/**
 * Drives the hero mark's glide.
 *
 * The numbers are researched, not invented. `direct_motion("a paper airplane
 * gliding")` returned anticipation 4, action 36, overshoot 3, settle 5 at
 * 60fps, and — the part that mattered most — "0% squash by default: keep the
 * paper-airplane silhouette rigid during the glide". A paper plane is stiff, so
 * the deformation instinct is wrong here and the motion lives entirely in
 * position and rotation.
 *
 * The path is an ARC, not a line. Straight interpolation between keys is the
 * clearest tell of machine-made motion, and a glide is the case where an arc is
 * least optional.
 *
 * Written as a single rAF loop rather than as keyframes because the mark
 * responds to the pointer: a bank that answers the cursor cannot be baked.
 */

export interface HeroMotionOptions {
  /** Artboard centre, where the mark rests. */
  origin?: { x: number; y: number };
  /** How far the glide travels, in artboard units. */
  amplitude?: { x: number; y: number };
  /** Seconds for one full glide cycle. */
  period?: number;
  /** Maximum bank in degrees. */
  bank?: number;
  /** How much the pointer pulls the mark, 0..1. */
  pointerPull?: number;
}

const DEFAULTS: Required<HeroMotionOptions> = {
  origin: { x: 210, y: 140 },
  // In ARTBOARD units, which is why these look large. The mark is 420 wide and
  // renders into roughly a 165px box, so travel is scaled by about 0.4 — an
  // amplitude of 26 moved it ten screen pixels over a six-second cycle, which
  // is slower than a clock hand and reads as static.
  amplitude: { x: 58, y: 34 },
  // 6.4s: long enough that the loop is not countable, which is what separates
  // ambient motion from a spinner.
  period: 5.2,
  bank: 7,
  pointerPull: 0.35,
};

export function useHeroMotion(rive: Rive | null, options: HeroMotionOptions = {}) {
  const [ready, setReady] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const pointer = useRef({ x: 0, y: 0 });
  const smoothed = useRef({ x: 0, y: 0 });

  // Settings live in a ref, and the effect depends on `rive` alone.
  //
  // Spreading them into a fresh object each render and then listing
  // `o.origin.x` and friends as dependencies looks careful but is the opposite:
  // the nested objects are new every time, so the effect tore down and
  // restarted on every render. `start` reset with it, and the glide never got
  // past its first few frames — the mark responded to the pointer, which is
  // read live, while appearing completely static otherwise.
  const settings = useRef<Required<HeroMotionOptions>>({ ...DEFAULTS, ...options });
  settings.current = { ...DEFAULTS, ...options };

  useEffect(() => {
    if (!rive) return;
    const o = settings.current;

    const vm = rive.viewModelInstance;
    if (!vm) return;

    const lift = vm.number('lift');
    const bank = vm.number('bank');
    const glide = vm.number('glide');
    if (!lift || !bank || !glide) return;
    setReady(true);

    // Reduced motion: place the mark at rest and stop. No rAF loop, and no
    // pointer listener either — a mark that chases the cursor is still motion,
    // and the preference is about motion, not about animation loops
    // specifically. The artwork stays fully visible; only the movement goes.
    if (reducedMotion) {
      glide.value = o.origin.x;
      lift.value = o.origin.y;
      bank.value = 0;
      return;
    }

    const onPointer = (e: PointerEvent) => {
      // Normalised to the viewport, so the pull is the same on any screen.
      pointer.current = {
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      };
    };
    window.addEventListener('pointermove', onPointer, { passive: true });

    const start = performance.now();
    let raf = 0;
    const tick = () => {
      const s = settings.current;
      const t = (performance.now() - start) / 1000;
      const phase = (t / s.period) * Math.PI * 2;

      // The arc. X and Y run at the same frequency a quarter-turn apart, which
      // traces an ellipse rather than a diagonal line — the difference between
      // a glide and a slide.
      const arcX = Math.cos(phase) * s.amplitude.x;
      const arcY = Math.sin(phase * 2) * s.amplitude.y * 0.5 +
                   Math.sin(phase) * s.amplitude.y * 0.5;

      // Pointer influence, eased toward the target rather than snapped. The
      // same frame-rate-independent law the camera engine uses: closing a
      // fraction of the remaining distance per second, not per frame.
      const k = 1 - Math.pow(1 - 0.9, 1 / 60);
      smoothed.current.x += (pointer.current.x - smoothed.current.x) * k * 4;
      smoothed.current.y += (pointer.current.y - smoothed.current.y) * k * 4;

      const px = smoothed.current.x * s.amplitude.x * s.pointerPull * 2;
      const py = smoothed.current.y * s.amplitude.y * s.pointerPull * 2;

      glide.value = s.origin.x + arcX + px;
      lift.value = s.origin.y + arcY + py;

      // Bank follows the DERIVATIVE of the path, so the plane leans into its
      // turn instead of leaning on a timer. A bank that does not match the
      // direction of travel is the thing that reads as wrong without anyone
      // being able to say why.
      const dx = -Math.sin(phase);
      bank.value = dx * s.bank + smoothed.current.x * s.bank * 0.6;

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onPointer);
    };
    // `rive` and the motion preference. The settings ref is read live inside
    // the loop, so an ordinary prop change takes effect without restarting the
    // clock; flipping the preference must tear the loop down, so it belongs
    // here rather than in the ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rive, reducedMotion]);

  return ready;
}
