import { describe, it, expect } from 'vitest';
import {
  approachCamera,
  clamp,
  followTarget,
  IDENTITY_CAMERA,
  rigTransform,
  sceneToScreen,
  screenToScene,
  zoomToFit,
  type CameraState,
} from './camera';

const VIEWPORT = { width: 1000, height: 600 };
const cam = (p: Partial<CameraState> = {}): CameraState => ({ ...IDENTITY_CAMERA, ...p });

describe('rigTransform', () => {
  it('centres the viewport when looking at the origin', () => {
    const t = rigTransform(cam(), VIEWPORT);
    expect([t.x, t.y]).toEqual([500, 300]);
  });

  it('moves the rig opposite to the camera', () => {
    // Camera pans right to x=100, so the world moves LEFT by 100.
    expect(rigTransform(cam({ lookX: 100 }), VIEWPORT).x).toBe(400);
  });

  it('emits scale as a PERCENTAGE, not a multiplier', () => {
    // Rive reads scale in inspector units: 100 == 1x. Emitting 2.2 would be
    // read as 2.2% and render an apparently empty frame.
    const t = rigTransform(cam({ zoom: 2.2 }), VIEWPORT);
    expect(t.scaleX).toBeCloseTo(220);
    expect(t.scaleY).toBeCloseTo(220);
    expect(rigTransform(cam(), VIEWPORT).scaleX).toBe(100);
  });

  it('inverts roll like every other camera axis', () => {
    expect(rigTransform(cam({ roll: 15 }), VIEWPORT).rotation).toBe(-15);
  });

  it('keeps the look-at point centred at every zoom', () => {
    for (const zoom of [1, 2, 4, 0.5]) {
      const p = sceneToScreen(200, 150, cam({ lookX: 200, lookY: 150, zoom }), VIEWPORT);
      expect(p.x).toBeCloseTo(500);
      expect(p.y).toBeCloseTo(300);
    }
  });

  it('does not divide by zero at zero zoom', () => {
    expect(rigTransform(cam({ zoom: 0 }), VIEWPORT).scaleX).toBeGreaterThan(0);
  });
});

describe('screen and scene conversion', () => {
  it('round-trips a point', () => {
    const c = cam({ lookX: 120, lookY: -40, zoom: 1.7 });
    const screen = sceneToScreen(310, 88, c, VIEWPORT);
    const back = screenToScene(screen.x, screen.y, c, VIEWPORT);
    expect(back.x).toBeCloseTo(310);
    expect(back.y).toBeCloseTo(88);
  });

  it('maps the viewport centre to the look-at point', () => {
    const c = cam({ lookX: 77, lookY: 33, zoom: 2 });
    const s = screenToScene(500, 300, c, VIEWPORT);
    expect(s.x).toBeCloseTo(77);
    expect(s.y).toBeCloseTo(33);
  });
});

describe('approachCamera', () => {
  it('moves toward the target', () => {
    const next = approachCamera(cam(), cam({ lookX: 100 }), 1 / 60);
    expect(next.lookX).toBeGreaterThan(0);
    expect(next.lookX).toBeLessThan(100);
  });

  it('is frame-rate independent', () => {
    // One 1/30s step must land in the same place as two 1/60s steps.
    // A naive per-frame lerp would converge twice as fast at 120fps.
    const target = cam({ lookX: 1000, zoom: 3 });
    const oneBig = approachCamera(cam(), target, 1 / 30);
    let twoSmall = cam();
    twoSmall = approachCamera(twoSmall, target, 1 / 60);
    twoSmall = approachCamera(twoSmall, target, 1 / 60);
    expect(twoSmall.lookX).toBeCloseTo(oneBig.lookX, 6);
    expect(twoSmall.zoom).toBeCloseTo(oneBig.zoom, 6);
  });

  it('converges rather than overshooting', () => {
    // Exponential approach never reaches the target exactly; after 400 frames
    // at 60fps the residual is ~1e-3 of the distance. Assert convergence and
    // no overshoot, which is the actual contract.
    let c = cam();
    for (let i = 0; i < 400; i++) c = approachCamera(c, cam({ lookX: 250 }), 1 / 60);
    expect(c.lookX).toBeCloseTo(250, 2);
    expect(c.lookX).toBeLessThanOrEqual(250);
  });

  it('a zero timestep changes nothing', () => {
    expect(approachCamera(cam(), cam({ lookX: 999 }), 0).lookX).toBe(0);
  });
});

describe('followTarget', () => {
  it('does not move while the subject is inside the dead zone', () => {
    // This is what stops a follow-cam jittering around a near-still subject.
    const c = cam();
    expect(followTarget(c, 20, 20, 40)).toBe(c);
  });

  it('moves only by the excess beyond the dead zone', () => {
    const next = followTarget(cam(), 100, 0, 40);
    expect(next.lookX).toBeCloseTo(60);
  });

  it('follows on both axes', () => {
    const next = followTarget(cam(), 0, -200, 50);
    expect(next.lookY).toBeCloseTo(-150);
  });
});

describe('zoomToFit', () => {
  it('fits a wide box by width', () => {
    const z = zoomToFit({ width: 2000, height: 100 }, VIEWPORT, 0);
    expect(z).toBeCloseTo(0.5);
  });

  it('fits a tall box by height', () => {
    const z = zoomToFit({ width: 100, height: 1200 }, VIEWPORT, 0);
    expect(z).toBeCloseTo(0.5);
  });

  it('margin reduces the zoom', () => {
    const tight = zoomToFit({ width: 500, height: 300 }, VIEWPORT, 0);
    const loose = zoomToFit({ width: 500, height: 300 }, VIEWPORT, 0.2);
    expect(loose).toBeLessThan(tight);
  });

  it('does not divide by zero on a degenerate box', () => {
    expect(zoomToFit({ width: 0, height: 0 }, VIEWPORT)).toBeGreaterThan(0);
  });
});

describe('clamp', () => {
  it('bounds a value', () => {
    expect([clamp(-1, 0, 10), clamp(5, 0, 10), clamp(99, 0, 10)]).toEqual([0, 5, 10]);
  });
});
