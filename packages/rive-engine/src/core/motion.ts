/**
 * Motion primitives shared by the camera engine and the UI kit.
 *
 * Rive draws; this decides how values get from where they are to where they
 * should be. Keeping it here — in `core`, which imports nothing — means a
 * button's hover lift and a camera's push-in obey the same law, and that law
 * can be unit-tested without a browser.
 *
 * The twelve principles of animation are not decoration in this file. Three of
 * them are expressible as pure functions of time and are implemented below:
 * slow in and slow out (`approach`), anticipation and follow-through
 * (`springStep`, whose overshoot is follow-through and whose negative initial
 * velocity gives anticipation), and secondary action (`stagger`).
 */

export { clamp, lerp } from './camera';
import { clamp, lerp } from './camera';

/**
 * Move a scalar toward a target with frame-rate-independent smoothing.
 *
 * `smoothing` is the fraction of the remaining distance closed per second, in
 * (0, 1). The `1 - (1 - s) ** dt` form is what makes it frame-rate independent:
 * a naive `lerp(current, target, s)` per frame converges twice as fast at
 * 120fps as at 60, so the same control feels different on different machines.
 *
 * This is the scalar form of `approachCamera`, and deliberately identical in
 * behaviour — one motion law, applied to cameras and to controls alike.
 */
export function approach(
  current: number,
  target: number,
  dtSeconds: number,
  smoothing = 0.85,
): number {
  const s = clamp(smoothing, 0, 0.999999);
  const k = 1 - Math.pow(1 - s, Math.max(dtSeconds, 0));
  return lerp(current, target, k);
}

export interface SpringState {
  value: number;
  velocity: number;
}

export interface SpringConfig {
  /** Higher is snappier. Roughly the square of the angular frequency. */
  stiffness: number;
  /** Higher settles sooner. At `2 * sqrt(stiffness)` the spring is critical. */
  damping: number;
  /** Heavier overshoots further and for longer. */
  mass: number;
}

/** A spring that overshoots a little — the follow-through of a real control. */
export const SPRING_SNAPPY: SpringConfig = { stiffness: 420, damping: 28, mass: 1 };
/** Critically damped: arrives fast and does not overshoot. For text and carets. */
export const SPRING_TIGHT: SpringConfig = { stiffness: 520, damping: 46, mass: 1 };
/** Slow and heavy, for large surfaces like panels. */
export const SPRING_SOFT: SpringConfig = { stiffness: 180, damping: 24, mass: 1 };

/**
 * Advance a damped spring by `dtSeconds`.
 *
 * Integrated in fixed sub-steps rather than one big step, because explicit
 * Euler integration goes unstable when `dt * stiffness / mass` gets large — and
 * `dt` genuinely does get large, every time a background tab is restored or the
 * main thread stalls. A stiff spring integrated in one 250 ms step does not
 * overshoot, it explodes.
 */
export function springStep(
  state: SpringState,
  target: number,
  dtSeconds: number,
  config: SpringConfig = SPRING_SNAPPY,
): SpringState {
  const dt = Math.min(Math.max(dtSeconds, 0), 0.25);
  const steps = Math.max(1, Math.ceil(dt / (1 / 240)));
  const h = dt / steps;

  let { value, velocity } = state;
  for (let i = 0; i < steps; i += 1) {
    const force = -config.stiffness * (value - target) - config.damping * velocity;
    velocity += (force / config.mass) * h;
    value += velocity * h;
  }

  // Snap when the motion is below a pixel-ish threshold in both position and
  // speed, so a spring cannot idle forever and keep a rAF loop alive.
  if (Math.abs(value - target) < 0.01 && Math.abs(velocity) < 0.05) {
    return { value: target, velocity: 0 };
  }
  return { value, velocity };
}

/** True once a spring has arrived and stopped. */
export function springAtRest(state: SpringState, target: number): boolean {
  return state.value === target && state.velocity === 0;
}

/**
 * Delay for the `index`th element of a staggered group, in seconds.
 *
 * Secondary action: a row of controls that all move at once reads as one block,
 * while the same row offset by a few frames reads as a group of things.
 * `falloff` below 1 compresses later delays so a long list does not end up
 * waiting a second for its last item.
 */
export function stagger(index: number, step = 0.05, falloff = 0.85): number {
  let total = 0;
  let d = step;
  for (let i = 0; i < index; i += 1) {
    total += d;
    d *= falloff;
  }
  return total;
}

/**
 * Map a value from one range to another, clamped to the output range.
 *
 * The UI kit works in the editor's units — opacity and scale as 0-100
 * percentages, positions in pixels — so nearly every channel is a remap of some
 * 0..1 interaction state onto a real geometric range.
 */
export function remap(
  value: number,
  inMin: number,
  inMax: number,
  outMin: number,
  outMax: number,
): number {
  if (inMax === inMin) return outMin;
  const t = (value - inMin) / (inMax - inMin);
  return clamp(lerp(outMin, outMax, t), Math.min(outMin, outMax), Math.max(outMin, outMax));
}
