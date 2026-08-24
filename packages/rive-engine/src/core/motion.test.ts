import { describe, expect, it } from 'vitest';
import {
  approach,
  remap,
  springAtRest,
  springStep,
  stagger,
  SPRING_SNAPPY,
  SPRING_TIGHT,
  type SpringState,
} from './motion';

/** Run a spring to rest, returning the path it took and how long it took. */
function settle(from: number, to: number, dt = 1 / 60, config = SPRING_SNAPPY) {
  let s: SpringState = { value: from, velocity: 0 };
  const path: number[] = [from];
  let frames = 0;
  while (!springAtRest(s, to) && frames < 6000) {
    s = springStep(s, to, dt, config);
    path.push(s.value);
    frames += 1;
  }
  return { path, frames, final: s };
}

describe('approach', () => {
  it('closes the gap toward the target', () => {
    expect(approach(0, 100, 1 / 60)).toBeGreaterThan(0);
    expect(approach(0, 100, 1 / 60)).toBeLessThan(100);
  });

  it('is frame-rate independent: same elapsed time, same result', () => {
    // One second, taken in 60 steps versus 120, must land in the same place.
    let a = 0;
    for (let i = 0; i < 60; i += 1) a = approach(a, 100, 1 / 60, 0.9);
    let b = 0;
    for (let i = 0; i < 120; i += 1) b = approach(b, 100, 1 / 120, 0.9);
    expect(Math.abs(a - b)).toBeLessThan(0.5);
  });

  it('never overshoots the target', () => {
    let v = 0;
    for (let i = 0; i < 500; i += 1) v = approach(v, 100, 1 / 60);
    expect(v).toBeLessThanOrEqual(100);
  });

  it('treats a negative dt as no time passing', () => {
    expect(approach(10, 100, -1)).toBe(10);
  });
});

describe('springStep', () => {
  it('reaches the target exactly and stops', () => {
    const { final } = settle(0, 100);
    expect(final.value).toBe(100);
    expect(final.velocity).toBe(0);
  });

  it('settles in well under a second at 60fps', () => {
    const { frames } = settle(0, 100);
    expect(frames).toBeLessThan(60);
  });

  it('overshoots with the snappy config — that is the follow-through', () => {
    const { path } = settle(0, 100, 1 / 60, SPRING_SNAPPY);
    expect(Math.max(...path)).toBeGreaterThan(100);
  });

  it('does not overshoot with the tight config', () => {
    const { path } = settle(0, 100, 1 / 60, SPRING_TIGHT);
    expect(Math.max(...path)).toBeLessThanOrEqual(100.01);
  });

  it('stays stable across a huge dt', () => {
    // A restored background tab hands us a several-second delta. Explicit Euler
    // in one step would diverge; the sub-stepping is what stops it.
    let s: SpringState = { value: 0, velocity: 0 };
    for (let i = 0; i < 10; i += 1) s = springStep(s, 100, 5);
    expect(Number.isFinite(s.value)).toBe(true);
    expect(Math.abs(s.value)).toBeLessThan(1000);
  });

  it('is stable when dt is zero', () => {
    const s = springStep({ value: 0, velocity: 0 }, 100, 0);
    expect(Number.isFinite(s.value)).toBe(true);
  });

  it('converges to the same place regardless of frame rate', () => {
    const at60 = settle(0, 100, 1 / 60).final.value;
    const at144 = settle(0, 100, 1 / 144).final.value;
    expect(at60).toBe(at144);
  });
});

describe('stagger', () => {
  it('gives the first element no delay', () => {
    expect(stagger(0)).toBe(0);
  });

  it('increases monotonically', () => {
    const delays = [0, 1, 2, 3, 4].map((i) => stagger(i));
    for (let i = 1; i < delays.length; i += 1) {
      expect(delays[i]!).toBeGreaterThan(delays[i - 1]!);
    }
  });

  it('compresses so a long list does not run away', () => {
    // Without falloff, 20 items at 50ms would be a full second of waiting.
    expect(stagger(20)).toBeLessThan(0.4);
  });
});

describe('remap', () => {
  it('maps the ends of the range', () => {
    expect(remap(0, 0, 100, 10, 20)).toBe(10);
    expect(remap(100, 0, 100, 10, 20)).toBe(20);
  });

  it('clamps outside the input range', () => {
    expect(remap(-50, 0, 100, 10, 20)).toBe(10);
    expect(remap(150, 0, 100, 10, 20)).toBe(20);
  });

  it('handles an inverted output range', () => {
    expect(remap(0, 0, 100, 20, 10)).toBe(20);
    expect(remap(100, 0, 100, 20, 10)).toBe(10);
  });

  it('does not divide by zero on a degenerate input range', () => {
    expect(remap(5, 3, 3, 10, 20)).toBe(10);
  });
});
