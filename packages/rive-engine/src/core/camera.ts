/**
 * Camera maths for the runtime — the mirror of `tools/genassets/camera.py`.
 *
 * The authoring side bakes a camera move into keyframes. This side drives a
 * camera *live*: follow a moving subject, respond to input, frame a target on
 * demand. Both need the same transform, so it exists in both languages and is
 * tested in both.
 *
 * Rive has no camera. A camera is simulated by transforming a rig that parents
 * the scene, inversely — move the camera right by moving the world left.
 *
 * Pure and dependency-free, like the rest of `core`.
 */

export interface CameraState {
  /** Scene point at the centre of frame. */
  lookX: number;
  lookY: number;
  /** 1 = fit, 2 = twice as close. */
  zoom: number;
  /** Camera roll in degrees. */
  roll: number;
}

export interface RigTransform {
  x: number;
  y: number;
  /** PERCENTAGE, not a multiplier — Rive reads scale in inspector units. */
  scaleX: number;
  scaleY: number;
  rotation: number;
}

export interface Viewport {
  width: number;
  height: number;
}

export const IDENTITY_CAMERA: CameraState = { lookX: 0, lookY: 0, zoom: 1, roll: 0 };

/**
 * The rig transform that puts `cam` on screen.
 *
 * Scale is emitted as a percentage (100 = 1x). Rive's property API takes
 * percent-displayed properties — scale, opacity, trim path, constraint
 * strength — in the units the inspector shows. Writing a 2.2x zoom as `2.2`
 * makes it 2.2%, which renders an apparently empty frame.
 */
export function rigTransform(cam: CameraState, viewport: Viewport): RigTransform {
  const z = Math.max(cam.zoom, 1e-6);
  return {
    x: viewport.width / 2 - cam.lookX * z,
    y: viewport.height / 2 - cam.lookY * z,
    scaleX: z * 100,
    scaleY: z * 100,
    rotation: -cam.roll,
  };
}

/** Where a scene point lands on screen under a camera. Inverse of the above. */
export function sceneToScreen(
  sceneX: number,
  sceneY: number,
  cam: CameraState,
  viewport: Viewport,
): { x: number; y: number } {
  const t = rigTransform(cam, viewport);
  const z = Math.max(cam.zoom, 1e-6);
  return { x: t.x + sceneX * z, y: t.y + sceneY * z };
}

/** Where a screen point sits in the scene. Needed to turn a click into a target. */
export function screenToScene(
  screenX: number,
  screenY: number,
  cam: CameraState,
  viewport: Viewport,
): { x: number; y: number } {
  const t = rigTransform(cam, viewport);
  const z = Math.max(cam.zoom, 1e-6);
  return { x: (screenX - t.x) / z, y: (screenY - t.y) / z };
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

/**
 * Move a camera toward a target with frame-rate-independent smoothing.
 *
 * `smoothing` is the fraction of remaining distance closed per second, in
 * (0, 1). The `1 - (1 - s) ** dt` form is what makes it frame-rate independent:
 * a naive `lerp(current, target, s)` per frame converges twice as fast at
 * 120fps as at 60, so the same camera feels different on different machines.
 */
export function approachCamera(
  current: CameraState,
  target: CameraState,
  dtSeconds: number,
  smoothing = 0.85,
): CameraState {
  const s = clamp(smoothing, 0, 0.999999);
  const k = 1 - Math.pow(1 - s, Math.max(dtSeconds, 0));
  return {
    lookX: lerp(current.lookX, target.lookX, k),
    lookY: lerp(current.lookY, target.lookY, k),
    zoom: lerp(current.zoom, target.zoom, k),
    roll: lerp(current.roll, target.roll, k),
  };
}

/**
 * A camera that keeps a subject inside a dead zone.
 *
 * The camera does not move while the subject is within `deadzone` of centre,
 * which is what stops a follow-cam from jittering around a nearly-still
 * subject. Past that, it moves only by the excess.
 */
export function followTarget(
  cam: CameraState,
  subjectX: number,
  subjectY: number,
  deadzone = 40,
): CameraState {
  const dx = subjectX - cam.lookX;
  const dy = subjectY - cam.lookY;
  const dist = Math.hypot(dx, dy);
  if (dist <= deadzone) return cam;
  const excess = (dist - deadzone) / dist;
  return { ...cam, lookX: cam.lookX + dx * excess, lookY: cam.lookY + dy * excess };
}

/**
 * The zoom that fits a scene rectangle into the viewport, with margin.
 *
 * Use to frame a subject: "put this bounding box on screen" is a more useful
 * instruction than "set zoom to 2.4".
 */
export function zoomToFit(
  box: { width: number; height: number },
  viewport: Viewport,
  margin = 0.1,
): number {
  const w = Math.max(box.width, 1e-6);
  const h = Math.max(box.height, 1e-6);
  const usableW = viewport.width * (1 - 2 * margin);
  const usableH = viewport.height * (1 - 2 * margin);
  return Math.min(usableW / w, usableH / h);
}
