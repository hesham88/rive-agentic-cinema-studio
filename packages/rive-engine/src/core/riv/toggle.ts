/**
 * A generated toggle — the spike's target.
 *
 * The point is not "we can emit a rectangle". It is that the file exposes a
 * **semantic contract** and hides its own mechanics, which is how Rive's own
 * production work is built:
 *
 *   > "As long as you keep the data contract the same … you can change the
 *   > health bar's appearance in the Rive Editor as much as you want without
 *   > updating or writing any additional code."
 *
 * So this artboard exposes exactly one thing — `checked` — and the motion,
 * easing and colour changes live inside the file. Contrast the hand-authored
 * `ui-kit.riv`, which exposes `knobX` and `on` and makes JavaScript do the
 * animating; that inverts the layers and defeats the runtime's auto-pause.
 *
 * Built bottom-up in three stages so each can be verified independently:
 *   `toggleStatic`   — geometry only, proves shapes and paints
 *   `toggleAnimated` — plus timelines and keyframes, proves animation
 *   `toggleRig`      — plus state machine and view model, proves the contract
 */

import { RivDocument, named, type Handle } from './encode';
import {
  FillRule,
  Interpolation,
  Loop,
  Prop,
  TypeKey,
  color,
  type PropertySpec,
} from './schema';
import type { PropValue } from './encode';

export interface ToggleStyle {
  width: number;
  height: number;
  /** Track colour when off, `#aarrggbb` or `#rrggbb`. */
  trackOff: string;
  /** Track colour when on. */
  trackOn: string;
  knob: string;
  /** Frames the knob takes to travel. 8 at 60fps ≈ 133ms — a UI-weight move. */
  travelFrames: number;
  fps: number;
}

export const DEFAULT_TOGGLE: ToggleStyle = {
  width: 68,
  height: 36,
  trackOff: '#ff2a3140',
  trackOn: '#ffea5a20',
  knob: '#fff2f5fa',
  travelFrames: 8,
  fps: 60,
};

type Props = Array<[PropertySpec, PropValue]>;

/**
 * Frames each pose timeline spans.
 *
 * A pose is a *held* value — both keyframes carry the same number — so the span
 * only has to be long enough for the timeline to be well-formed. The visible
 * movement comes from the state machine's transition Duration, not from here.
 */
const POSE_FRAMES = 24;

/**
 * Geometry shared by every stage.
 *
 * Returns the handles later stages animate. The knob's rest position is the
 * left inset; the artboard's origin properties are left at their defaults
 * because a UI widget is positioned by its container, not by itself.
 */
function buildBody(
  doc: RivDocument,
  style: ToggleStyle,
  /** Set only by stage 3; a geometry-only file binds nothing. */
  bind?: { viewModelId: number; defaultStateMachineId: number },
) {
  const inset = style.height / 2;
  const artboard = doc.add(TypeKey.artboard, [
    [Prop.name, 'toggle'],
    [Prop.width, style.width],
    [Prop.height, style.height],
    [Prop.x, 0],
    [Prop.y, 0],
    ...((bind
      ? [
          [Prop.viewModelId, bind.viewModelId],
          [Prop.defaultStateMachineId, bind.defaultStateMachineId],
        ]
      : []) as Props),
  ] as Props);

  const track = doc.add(TypeKey.shape, [
    ...named('track', artboard),
    [Prop.x, style.width / 2],
    [Prop.y, style.height / 2],
  ] as Props);
  doc.add(TypeKey.rectangle, [
    ...named('track-path', track),
    [Prop.pathWidth, style.width],
    [Prop.pathHeight, style.height],
    // Radius = half the height gives a true pill regardless of size.
    [Prop.cornerRadiusTL, style.height / 2],
    [Prop.linkCornerRadius, true],
  ] as Props);
  const trackFill = doc.add(TypeKey.fill, [
    ...named('track-fill', track),
    [Prop.fillRule, FillRule.nonZero],
  ] as Props);
  const trackColor = doc.add(TypeKey.solidColor, [
    ...named('track-color', trackFill),
    [Prop.colorValue, color(style.trackOff)],
  ] as Props);

  const knob = doc.add(TypeKey.shape, [
    ...named('knob', artboard),
    [Prop.x, inset],
    [Prop.y, style.height / 2],
  ] as Props);
  doc.add(TypeKey.ellipse, [
    ...named('knob-path', knob),
    [Prop.pathWidth, style.height - 8],
    [Prop.pathHeight, style.height - 8],
  ] as Props);
  const knobFill = doc.add(TypeKey.fill, [
    ...named('knob-fill', knob),
    [Prop.fillRule, FillRule.nonZero],
  ] as Props);
  doc.add(TypeKey.solidColor, [
    ...named('knob-color', knobFill),
    [Prop.colorValue, color(style.knob)],
  ] as Props);

  return { artboard, track, trackColor, knob, knobX: { left: inset, right: style.width - inset } };
}

/** Stage 1 — geometry only. Nothing moves. */
export function toggleStatic(style: ToggleStyle = DEFAULT_TOGGLE): Uint8Array {
  const doc = new RivDocument();
  doc.add(TypeKey.backboard);
  buildBody(doc, style);
  return doc.encode();
}

/**
 * Stage 2 — two timelines, keyframed.
 *
 * `off` and `on` each hold the knob at one end. A state machine will later
 * transition between them with a real Duration, which is where the easing
 * actually comes from — this is why the timelines themselves are single-pose
 * and why Rive's docs say to build "focused timelines with limited keyed
 * properties".
 */
export function toggleAnimated(style: ToggleStyle = DEFAULT_TOGGLE): Uint8Array {
  const doc = new RivDocument();
  doc.add(TypeKey.backboard);
  const body = buildBody(doc, style);
  addPoseTimelines(doc, body, style);
  return doc.encode();
}

function addPoseTimelines(
  doc: RivDocument,
  body: ReturnType<typeof buildBody>,
  style: ToggleStyle,
) {
  const poses: Array<{ name: string; x: number; track: string }> = [
    { name: 'off', x: body.knobX.left, track: style.trackOff },
    { name: 'on', x: body.knobX.right, track: style.trackOn },
  ];

  const animations: Handle[] = [];
  for (const pose of poses) {
    // `duration` is in frames and must span the keys, or the timeline ends
    // before its second keyframe is ever reached.
    const anim = doc.add(TypeKey.linearAnimation, [
      [Prop.animationName, pose.name],
      [Prop.fps, style.fps],
      [Prop.duration, POSE_FRAMES],
      [Prop.speed, 1],
      [Prop.loopValue, Loop.oneShot],
    ] as Props);

    // Knob position. TWO keyframes, not one: a property with a single key has
    // nothing to interpolate toward, so the state holds a constant and the
    // transition between states has no visible effect. The editor writes a
    // start and an end key for every keyed property, and that is why.
    doc.add(TypeKey.keyedObject, [[Prop.keyedObjectId, body.knob.index]] as Props);
    doc.add(TypeKey.keyedProperty, [[Prop.keyedPropertyKey, Prop.x.key]] as Props);
    for (const frame of [0, POSE_FRAMES]) {
      doc.add(TypeKey.keyFrameDouble, [
        [Prop.frame, frame],
        [Prop.interpolationType, Interpolation.linear],
        [Prop.keyFrameDoubleValue, pose.x],
      ] as Props);
    }

    // Track colour, through KeyFrameColor — a different object from
    // KeyFrameDouble, with its own value key. Pushing an ARGB integer through
    // the double key stores it as a float32 and the colour never animates.
    doc.add(TypeKey.keyedObject, [[Prop.keyedObjectId, body.trackColor.index]] as Props);
    doc.add(TypeKey.keyedProperty, [[Prop.keyedPropertyKey, Prop.colorValue.key]] as Props);
    for (const frame of [0, POSE_FRAMES]) {
      doc.add(TypeKey.keyFrameColor, [
        [Prop.frame, frame],
        [Prop.interpolationType, Interpolation.linear],
        [Prop.keyFrameColorValue, color(pose.track)],
      ] as Props);
    }

    animations.push(anim);
  }
  return animations;
}

/**
 * Stage 3 — the semantic contract.
 *
 * The file exposes exactly one thing: a boolean view-model property named
 * `checked`. Everything else — where the knob sits, what colour the track is,
 * how long the change takes — lives inside the file, which is the whole point:
 *
 *   > "As long as you keep the data contract the same ... you can change the
 *   > health bar's appearance in the Rive Editor as much as you want without
 *   > updating or writing any additional code."
 *
 * Object ORDER below is copied from a decoded editor export, not inferred.
 * Three details are load-bearing and each was verified against
 * `paper-plane-interactive.riv`:
 *
 *   1. View models are emitted BEFORE the artboard, at the top of the stream.
 *   2. Three separate index spaces: `viewModelId` indexes the file's view-model
 *      list, an instance value's `parentId` indexes the file's INSTANCE list
 *      (not the artboard's objects), and `viewModelPropertyId` indexes that
 *      view model's property list in declaration order.
 *   3. A transition condition is a run of five objects in a fixed order,
 *      because `File::read` binds a `DataBind` to the immediately preceding
 *      non-DataBind object.
 */
/**
 * Property id for `checked` — a 0-based INDEX into ToggleVM's property list.
 *
 * `ViewModel::property(size_t index)` indexes directly, and
 * `ViewModelInstance::propertyValue(id)` matches that same id, so declaration
 * order decides it. `checked` is our only property, hence 0.
 *
 * The editor's `paper-plane-interactive.riv` binds `isHovered` with the path
 * `[0, 1]` — `0` being its view-model id and `1` being `isHovered`'s index,
 * since `boost` is declared first.
 */
const VM_PROPERTY_CHECKED = 0;

export function toggleRig(style: ToggleStyle = DEFAULT_TOGGLE): Uint8Array {
  const doc = new RivDocument();
  doc.add(TypeKey.backboard);

  // --- View model: the entire public surface of this file. ---------------
  doc.add(TypeKey.viewModel, [
    [Prop.viewModelComponentName, 'ToggleVM'],
  ] as Props);
  // Property index 0 within ToggleVM.
  doc.add(TypeKey.viewModelPropertyBoolean, [
    [Prop.viewModelComponentName, 'checked'],
  ] as Props);

  // Two instances, matching what the editor emits. `autoBind` picks "Default";
  // the extra "Instance" exists because the editor always writes both, and a
  // file that differs structurally from an editor export is a file whose
  // behaviour we cannot reason about.
  for (const [index, instanceName] of ['Instance', 'Default'].entries()) {
    doc.add(TypeKey.viewModelInstance, [
      [Prop.instanceViewModelId, 0],
      [Prop.name, instanceName],
    ] as Props);
    doc.add(TypeKey.viewModelInstanceBoolean, [
      [Prop.parentId, index],
      [Prop.viewModelPropertyId, VM_PROPERTY_CHECKED],
      [Prop.instanceBooleanValue, false],
    ] as Props);
  }

  // --- Artboard and geometry ---------------------------------------------
  const body = buildBody(doc, style, {
    viewModelId: 0,
    defaultStateMachineId: 0,
  });
  addPoseTimelines(doc, body, style);

  // --- State machine ------------------------------------------------------
  // `StateMachine` takes Animation.name (55), while the LAYER takes
  // StateMachineComponent.name (138). Different keys on different objects.
  doc.add(TypeKey.stateMachine, [[Prop.animationName, 'State Machine 1']] as Props);
  doc.add(TypeKey.stateMachineLayer, [[Prop.stateMachineName, 'Layer 1']] as Props);

  // States are emitted in a fixed order, and `stateToId` indexes THIS list:
  //   0 = Any, 1 = Entry, 2 = Exit, 3 = off, 4 = on
  const OFF_STATE = 3;
  const ON_STATE = 4;

  doc.add(TypeKey.anyState);
  doc.add(TypeKey.entryState);
  // Entry goes straight to `off`, so the toggle starts in a defined pose.
  doc.add(TypeKey.stateTransition, [[Prop.stateToId, OFF_STATE]] as Props);
  doc.add(TypeKey.exitState);

  // `off` --(checked == true)--> `on`
  doc.add(TypeKey.animationState, [[Prop.animationId, 0]] as Props);
  addConditionalTransition(doc, ON_STATE, true, style.travelFrames);

  // `on` --(checked == false)--> `off`
  doc.add(TypeKey.animationState, [[Prop.animationId, 1]] as Props);
  addConditionalTransition(doc, OFF_STATE, false, style.travelFrames);

  return doc.encode();
}

/**
 * A transition guarded by `checked`, with a real duration.
 *
 * Duration is set explicitly because it defaults to **0** — an instant snap.
 * None of the files this project authored by hand set it, which is exactly why
 * their state changes read as switching rather than moving.
 *
 * The five objects after the transition are its condition, and their order is
 * not stylistic: the `DataBindContext` binds to whatever non-DataBind object
 * precedes it.
 */
function addConditionalTransition(
  doc: RivDocument,
  toState: number,
  expected: boolean,
  frames: number,
) {
  doc.add(TypeKey.stateTransition, [
    [Prop.stateToId, toState],
    [Prop.transitionDuration, frames],
  ] as Props);

  doc.add(TypeKey.transitionViewModelCondition);
  doc.add(TypeKey.bindablePropertyBoolean);
  doc.add(TypeKey.dataBindContext, [
    // 634 is the bindable's own `propertyValue` — the slot being fed.
    [Prop.dataBindPropertyKey, Prop.bindableBooleanValue.key],
    // A List<Id> of varuints, and it must have at LEAST two elements.
    //
    // `DataContext::tryGetViewModelProperty` matches `path[0]` against the
    // instance's *viewModelId*, returns null immediately when
    // `path.size() == 1`, then walks the middle entries as nested view models
    // and resolves `path.back()` as the property id. So the shape is
    // `[viewModelId, ...nested, propertyId]`.
    //
    // A one-element path — the obvious first guess — parses, renders, and
    // silently never binds: the file loads, the property enumerates, and the
    // transition simply never fires.
    [Prop.sourcePathIds, new Uint8Array([0, VM_PROPERTY_CHECKED])],
  ] as Props);
  doc.add(TypeKey.transitionPropertyViewModelComparator);
  doc.add(TypeKey.transitionValueBooleanComparator, [
    [Prop.comparatorBooleanValue, expected],
  ] as Props);
}
