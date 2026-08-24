import { describe, expect, it } from 'vitest';
import { flicker, kelvinToCss, kelvinToRgb, swing } from './light';

/**
 * The important tests here are the cross-language ones.
 *
 * `flicker` and `kelvinToRgb` are implemented TWICE — once in Python for
 * authoring, once here for runtime. If they ever drift, a lamp baked into
 * keyframes and the same lamp driven live will disagree, and the bug will look
 * like a rendering problem rather than a constant that got edited on one side
 * only. The expected values below were generated from the Python engine.
 */

/** From `genassets.light.flicker(f, seed=3)` for f in 0..7. */
const PY_FLICKER_SEED3 = [
  1.0303755551, 1.0006672476, 0.9945763932, 1.0252447319,
  1.035110394, 0.9924786298, 0.9450407012, 0.9313042664,
];

/** From `genassets.light.kelvin_to_rgb()`. */
const PY_KELVIN: Array<[number, [number, number, number]]> = [
  [1900, [255, 132, 0]],
  [2800, [255, 170, 95]],
  [5600, [255, 239, 225]],
  [7500, [230, 235, 255]],
];

describe('flicker', () => {
  it('matches the Python engine exactly', () => {
    PY_FLICKER_SEED3.forEach((expected, frame) => {
      expect(flicker(frame, { seed: 3 })).toBeCloseTo(expected, 9);
    });
  });

  it('is reproducible', () => {
    const a = Array.from({ length: 100 }, (_, f) => flicker(f, { seed: 7 }));
    const b = Array.from({ length: 100 }, (_, f) => flicker(f, { seed: 7 }));
    expect(a).toEqual(b);
  });

  it('separates seeds', () => {
    expect(flicker(10, { seed: 1 })).not.toBe(flicker(10, { seed: 2 }));
  });

  it('stays inside the amplitude band', () => {
    for (let f = 0; f < 1000; f += 1) {
      const v = flicker(f, { amplitude: 0.2 });
      expect(v).toBeGreaterThanOrEqual(0.8 - 1e-9);
      expect(v).toBeLessThanOrEqual(1.2 + 1e-9);
    }
  });

  it('never goes negative', () => {
    // A negative intensity would invert the gradient rather than dim it.
    for (let f = 0; f < 400; f += 1) {
      expect(flicker(f, { amplitude: 5, base: 0.1 })).toBeGreaterThanOrEqual(0);
    }
  });

  it('does not visibly repeat within a couple of seconds', () => {
    const a = Array.from({ length: 60 }, (_, f) => flicker(f));
    const b = Array.from({ length: 60 }, (_, f) => flicker(f + 60));
    expect(a).not.toEqual(b);
  });
});

describe('kelvinToRgb', () => {
  it('matches the Python engine', () => {
    for (const [k, expected] of PY_KELVIN) {
      expect(kelvinToRgb(k)).toEqual(expected);
    }
  });

  it('gets warmer as kelvin drops', () => {
    const [, , candleB] = kelvinToRgb(1900);
    const [, , skyB] = kelvinToRgb(7500);
    expect(skyB).toBeGreaterThan(candleB);
  });

  it('clamps rather than throwing on absurd input', () => {
    expect(kelvinToRgb(-500)).toEqual(kelvinToRgb(1000));
    expect(kelvinToRgb(1e9)).toEqual(kelvinToRgb(40000));
  });

  it('keeps every channel in range', () => {
    for (let k = 1000; k <= 20000; k += 250) {
      for (const c of kelvinToRgb(k)) {
        expect(c).toBeGreaterThanOrEqual(0);
        expect(c).toBeLessThanOrEqual(255);
      }
    }
  });

  it('renders CSS', () => {
    expect(kelvinToCss(1900)).toBe('rgb(255 132 0)');
  });
});

describe('swing', () => {
  it('starts at rest', () => {
    expect(swing(0)).toBeCloseTo(0, 9);
  });

  it('decays toward rest', () => {
    // Sampled at the same phase each period, so only the decay differs.
    const first = Math.abs(swing(0.4, { period: 1.6, damping: 0.45 }));
    const later = Math.abs(swing(0.4 + 1.6 * 3, { period: 1.6, damping: 0.45 }));
    expect(later).toBeLessThan(first);
  });

  it('never exceeds its amplitude', () => {
    for (let t = 0; t < 20; t += 0.01) {
      expect(Math.abs(swing(t, { amplitude: 8 }))).toBeLessThanOrEqual(8 + 1e-9);
    }
  });

  it('changes sign — it swings, it does not drift', () => {
    const samples = Array.from({ length: 200 }, (_, i) => swing(i * 0.02));
    expect(samples.some((v) => v > 0)).toBe(true);
    expect(samples.some((v) => v < 0)).toBe(true);
  });
});
