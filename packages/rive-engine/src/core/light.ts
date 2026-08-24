/**
 * The light engine's runtime half.
 *
 * `tools/genassets/genassets/light.py` decides what a light looks like at
 * author time — gradient stops, colour temperature, rig geometry. This decides
 * how it BEHAVES at run time, and the two share one definition of flicker so a
 * lamp animates the same way whether it was baked into keyframes or driven live.
 *
 * Pure, like the rest of `core`: no Rive, no React, no DOM.
 */

/**
 * A reproducible flame flicker as a multiplier on intensity.
 *
 * A sum of three incommensurate sines — their periods share no common factor,
 * so the pattern never visibly repeats, but it is entirely determined by
 * `frame` and `seed`. Deliberately NOT random: the Python authoring side must
 * be able to bake the identical curve into keyframes, and `Math.random()` would
 * make the two diverge.
 *
 * Mirrors `light.flicker()` in the Python engine; the constants must stay in
 * step with it.
 */
export function flicker(
  frame: number,
  { seed = 0, amplitude = 0.12, base = 1 }: {
    seed?: number;
    amplitude?: number;
    base?: number;
  } = {},
): number {
  const phase = seed * 0.7391;
  const v =
    (Math.sin(frame * 0.31 + phase) +
      0.6 * Math.sin(frame * 0.73 + phase * 2.1) +
      0.3 * Math.sin(frame * 1.55 + phase * 3.7)) /
    1.9;
  return Math.max(0, base + amplitude * v);
}

/**
 * Approximate the sRGB colour of a blackbody radiator at `kelvin`.
 *
 * Tanner Helland's piecewise fit, clamped to 1000-40000 K. Mirrors
 * `light.kelvin_to_rgb()` so a colour picked in the pipeline and a colour
 * computed in the browser agree.
 */
export function kelvinToRgb(kelvin: number): [number, number, number] {
  const t = Math.max(1000, Math.min(40000, kelvin)) / 100;
  const clamp = (v: number) => Math.round(Math.max(0, Math.min(255, v)));

  const r = t <= 66 ? 255 : 329.698727446 * Math.pow(t - 60, -0.1332047592);
  const g =
    t <= 66
      ? 99.4708025861 * Math.log(t) - 161.1195681661
      : 288.1221695283 * Math.pow(t - 60, -0.0755148492);
  const b =
    t >= 66 ? 255 : t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;

  return [clamp(r), clamp(g), clamp(b)];
}

/** Blackbody colour as a CSS `rgb()` string. */
export function kelvinToCss(kelvin: number): string {
  const [r, g, b] = kelvinToRgb(kelvin);
  return `rgb(${r} ${g} ${b})`;
}

/**
 * A pendulum swing angle in degrees, decaying toward rest.
 *
 * `damping` is the fraction of amplitude remaining after one second. A lantern
 * knocked once should settle; one that swings forever reads as a loop, not as
 * an object with mass.
 */
export function swing(
  seconds: number,
  { amplitude = 8, period = 1.6, damping = 0.45 }: {
    amplitude?: number;
    period?: number;
    damping?: number;
  } = {},
): number {
  const decay = Math.pow(damping, seconds);
  return amplitude * decay * Math.sin((2 * Math.PI * seconds) / period);
}
