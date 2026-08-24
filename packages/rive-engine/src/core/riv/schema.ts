/**
 * The subset of Rive's core schema this encoder writes.
 *
 * Every key here was extracted from the 371 definition files in
 * `rive-runtime/dev/defs`, not guessed. The full extraction lives at
 * `_OPERATIONS/study/rive-schema.json` (371 object types, 870 properties); this
 * file carries only what we emit, so a wrong key is a compile error rather than
 * a file that silently fails to load.
 *
 * A property marked `runtime: false` in the defs is editor-only and must NEVER
 * be written — none of those appear below.
 */

import { FieldType, type FieldTypeId } from './writer';

/** Core object type keys — the first varuint of every serialized object. */
export const TypeKey = {
  artboard: 1,
  node: 2,
  shape: 3,
  ellipse: 4,
  rectangle: 7,
  solidColor: 18,
  fill: 20,
  backboard: 23,
  stroke: 24,
  keyedObject: 25,
  keyedProperty: 26,
  keyFrameDouble: 30,
  keyFrameColor: 37,
  linearAnimation: 31,
  stateMachine: 53,
  stateMachineLayer: 57,
  animationState: 61,
  stateTransition: 65,
  keyFrameBool: 84,
  cubicInterpolator: 139,
  // Decoding a real export corrected these: AnyState is 62 and EntryState is
  // 63, the reverse of what the def filenames suggest.
  anyState: 62,
  entryState: 63,
  exitState: 64,
  viewModel: 435,
  viewModelPropertyNumber: 431,
  viewModelPropertyBoolean: 448,
  viewModelInstance: 437,
  viewModelInstanceNumber: 442,
  viewModelInstanceBoolean: 449,
  // A transition condition is a run of five objects; see 08-editor-structure.
  transitionViewModelCondition: 482,
  bindablePropertyBoolean: 472,
  dataBindContext: 447,
  transitionPropertyViewModelComparator: 479,
  transitionValueBooleanComparator: 481,
  stateMachineListenerSingle: 114,
  dataBind: 446,
  stateMachineBool: 59,
} as const;

/**
 * Property keys, with the backing type each is written as.
 *
 * The type decides both the wire encoding and the two-bit entry this property
 * needs in the header's table of contents.
 */
export interface PropertySpec {
  key: number;
  field: FieldTypeId;
}

const p = (key: number, field: FieldTypeId): PropertySpec => ({ key, field });

export const Prop = {
  // Component
  name: p(4, FieldType.string),
  parentId: p(5, FieldType.uint),

  // Animation and StateMachineComponent do NOT extend Component, so they carry
  // their own name keys. Using key 4 on them writes a property the object does
  // not own: the file still loads, but the name comes back empty.
  animationName: p(55, FieldType.string),
  stateMachineName: p(138, FieldType.string),

  // Artboard / LayoutComponent
  width: p(7, FieldType.double),
  height: p(8, FieldType.double),
  originX: p(11, FieldType.double),
  originY: p(12, FieldType.double),
  defaultStateMachineId: p(236, FieldType.uint),
  viewModelId: p(583, FieldType.uint),

  // Node / TransformComponent
  x: p(13, FieldType.double),
  y: p(14, FieldType.double),
  rotation: p(15, FieldType.double),
  scaleX: p(16, FieldType.double),
  scaleY: p(17, FieldType.double),
  opacity: p(18, FieldType.double),

  // ParametricPath — note these differ from the artboard's width/height keys
  pathWidth: p(20, FieldType.double),
  pathHeight: p(21, FieldType.double),
  pathOriginX: p(123, FieldType.double),
  pathOriginY: p(124, FieldType.double),

  // Rectangle
  cornerRadiusTL: p(31, FieldType.double),
  cornerRadiusTR: p(161, FieldType.double),
  cornerRadiusBL: p(162, FieldType.double),
  cornerRadiusBR: p(163, FieldType.double),
  linkCornerRadius: p(164, FieldType.uint),

  // Paint
  colorValue: p(37, FieldType.color),
  fillRule: p(40, FieldType.uint),
  isVisible: p(41, FieldType.uint),

  // LinearAnimation
  fps: p(56, FieldType.uint),
  duration: p(57, FieldType.uint),
  speed: p(58, FieldType.double),
  loopValue: p(59, FieldType.uint),
  workStart: p(60, FieldType.uint),
  workEnd: p(61, FieldType.uint),
  enableWorkArea: p(62, FieldType.uint),

  // Keyframes
  keyedObjectId: p(51, FieldType.uint),
  keyedPropertyKey: p(53, FieldType.uint),
  frame: p(67, FieldType.uint),
  interpolationType: p(68, FieldType.uint),
  interpolatorId: p(69, FieldType.uint),
  keyFrameDoubleValue: p(70, FieldType.double),
  // Colour keyframes are a DIFFERENT object (tk 37) with their own value key.
  // Pushing an ARGB integer through keyFrameDouble stores it as a float32 and
  // the colour never animates.
  keyFrameColorValue: p(88, FieldType.color),
  keyFrameBoolValue: p(181, FieldType.uint),

  // CubicInterpolator
  cubicX1: p(63, FieldType.double),
  cubicY1: p(64, FieldType.double),
  cubicX2: p(65, FieldType.double),
  cubicY2: p(66, FieldType.double),

  // State machine
  animationId: p(149, FieldType.uint),
  stateToId: p(151, FieldType.uint),
  transitionFlags: p(152, FieldType.uint),
  transitionDuration: p(158, FieldType.uint),
  exitTime: p(160, FieldType.uint),
  transitionInterpolationType: p(349, FieldType.uint),
  transitionInterpolatorId: p(350, FieldType.uint),

  // View model. `ViewModelComponent.name` is key 557 — distinct from
  // `Component.name` (4), which ViewModelInstance uses for ITS name.
  viewModelComponentName: p(557, FieldType.string),
  viewModelType: p(981, FieldType.uint),
  instanceViewModelId: p(566, FieldType.uint),
  viewModelPropertyId: p(554, FieldType.uint),
  instanceBooleanValue: p(593, FieldType.uint),

  // Data bind
  dataBindPropertyKey: p(586, FieldType.uint),
  dataBindFlags: p(587, FieldType.uint),
  sourcePathIds: p(588, FieldType.string),

  // Transition conditions
  bindableBooleanValue: p(634, FieldType.uint),
  comparatorBooleanValue: p(647, FieldType.uint),
  listenerTargetId: p(224, FieldType.uint),
} as const;

export type PropName = keyof typeof Prop;

/** Loop modes for a LinearAnimation's `loopValue`. */
export const Loop = { oneShot: 0, loop: 1, pingPong: 2 } as const;

/** Keyframe interpolation, matching `KeyFrameInterpolation` in the runtime. */
export const Interpolation = { hold: 0, linear: 1, cubic: 2 } as const;

/**
 * Fill rules. `clockwise` is Rive-specific and is REQUIRED for feathering — a
 * feathered fill with any other rule silently does nothing.
 */
export const FillRule = { nonZero: 0, evenOdd: 1, clockwise: 2 } as const;

/** Pack `#aarrggbb` into the uint32 a Color property expects. */
export function argb(a: number, r: number, g: number, b: number): number {
  return (((a & 0xff) << 24) | ((r & 0xff) << 16) | ((g & 0xff) << 8) | (b & 0xff)) >>> 0;
}

/** Parse `#aarrggbb` or `#rrggbb` (assumed opaque) into a Color value. */
export function color(hex: string): number {
  const h = hex.replace('#', '').trim();
  if (h.length === 8) {
    return argb(
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
      parseInt(h.slice(6, 8), 16),
    );
  }
  if (h.length === 6) {
    return argb(255, parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16));
  }
  throw new RangeError(`expected #aarrggbb or #rrggbb, got "${hex}"`);
}
