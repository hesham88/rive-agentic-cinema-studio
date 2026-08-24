"""Motion craft — the difference between animated and well animated.

Everything here encodes a principle that animators apply by instinct and that
generated animation almost always misses. Each is a small amount of arithmetic;
what matters is knowing which one a shot needs.

  stagger        Elements that move together read as a single object. Offsetting
                 their starts by a few frames makes a group read as many things.
  anticipation   A small counter-move before the main one. Nothing in the world
                 accelerates from rest instantly; the wind-up is what sells the
                 launch.
  overshoot      Motion that stops exactly on its target reads as mechanical.
                 Passing slightly and settling back reads as physical.
  follow_through Subordinate parts arrive after the thing that drags them —
                 the flame trails the rocket, not the other way round.
  arcs           Nothing alive moves in a straight line. Linear interpolation
                 between two keys is the single clearest tell of machine-made
                 motion; a thrown object, a swinging limb and a camera whip all
                 travel on curves.
  parallax       Depth is rate: far things move less than near things under the
                 same camera move. Without it, a pan is a flat slide.

All pure: keyframe dicts in, keyframe dicts out, ready for
`animation_editor.modifyKeyFrames`. No Rive, no I/O.

Scale and opacity are emitted as PERCENTAGES (100 = 1x), matching Rive's
property API — a multiplier written there is read as a percent and the object
effectively vanishes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .camera import PROP, ease

__all__ = [
    "Keyframe",
    "arc",
    "stagger",
    "anticipate",
    "overshoot",
    "follow_through",
    "parallax_factor",
    "parallax_shift",
    "breathe",
    "PERCENT_PROPS",
]

#: Properties Rive expresses as 0-100 percentages rather than raw multipliers.
PERCENT_PROPS = {PROP["scaleX"], PROP["scaleY"], PROP["opacity"]}

Keyframe = dict


def _kf(object_id: str, prop: int, frame: int, value: float,
        easing: str = "ease") -> Keyframe:
    return {
        "objectId": object_id,
        "propertyKey": prop,
        "frame": max(0, int(round(frame))),
        "value": round(value, 3),
        "interpolationType": "cubic",
        "cubicParams": ease(easing),
    }


def arc(
    object_id: str,
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    start_frame: int = 0,
    duration: int = 30,
    bow: float = 0.25,
    samples: int = 6,
    easing: str = "easeInOut",
) -> list[Keyframe]:
    """Move between two points along a CURVE rather than a straight line.

    Rive interpolates linearly between position keyframes, so two keys always
    produce a straight path however the easing is shaped — easing controls
    *speed*, never *route*. The only way to get an arc is to emit intermediate
    keys along one.

    `bow` is the curve depth as a fraction of the distance travelled,
    perpendicular to the line between the points. Positive bows one way,
    negative the other; 0.2-0.35 reads as natural, and 0 degenerates to a
    straight line.

    `samples` is how many intermediate keys describe the curve. Six is enough
    for a smooth read at typical speeds — each key is a handle in the editor, so
    more is not better.
    """
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0

    # Control point: the midpoint pushed perpendicular to the chord. A quadratic
    # bezier through it is the simplest curve that is still adjustable by feel.
    cx = (x0 + x1) / 2 - dy * bow
    cy = (y0 + y1) / 2 + dx * bow

    out: list[Keyframe] = []
    for i in range(samples + 1):
        t = i / samples
        u = 1 - t
        px = u * u * x0 + 2 * u * t * cx + t * t * x1
        py = u * u * y0 + 2 * u * t * cy + t * t * y1
        frame = start_frame + duration * t
        # Only the endpoints carry the easing; the interior keys are linear so
        # the shaped curve is not eased twice, which would stutter the travel.
        curve = easing if i in (0, samples) else "linear"
        out.append(_kf(object_id, PROP["x"], frame, px, curve))
        out.append(_kf(object_id, PROP["y"], frame, py, curve))
    return out


def stagger(
    object_ids: list[str],
    prop: int,
    *,
    start_value: float,
    end_value: float,
    start_frame: int = 0,
    duration: int = 24,
    step: int = 4,
    easing: str = "backOut",
    reverse: bool = False,
) -> list[Keyframe]:
    """Animate several objects with an offset start, so they cascade.

    `step` is the offset between neighbours in frames. Small values (3-6) read
    as one gesture with texture; large values (12+) read as separate events.

    Use `reverse` when the cascade should run from the far end — a list closing
    should collapse in the opposite order to the one it opened in, or it feels
    like it is being read twice.
    """
    ids = list(reversed(object_ids)) if reverse else object_ids
    out: list[Keyframe] = []
    for i, oid in enumerate(ids):
        begin = start_frame + i * step
        out.append(_kf(oid, prop, begin, start_value, easing))
        out.append(_kf(oid, prop, begin + duration, end_value, easing))
    return out


def anticipate(
    object_id: str,
    prop: int,
    *,
    rest: float,
    target: float,
    start_frame: int = 0,
    wind_up: int = 8,
    action: int = 20,
    amount: float = 0.18,
) -> list[Keyframe]:
    """Wind up against the motion, then commit.

    `amount` is the counter-move as a fraction of the main travel. Around 0.15-0.25
    is legible without looking like a mistake; past ~0.4 it reads as two moves.

    The wind-up eases OUT (it decelerates into the turnaround) and the action
    eases IN (it accelerates away). Using one curve for both is what makes
    anticipation look like a wobble instead of a preparation.
    """
    travel = target - rest
    back = rest - travel * amount
    return [
        _kf(object_id, prop, start_frame, rest, "easeOut"),
        _kf(object_id, prop, start_frame + wind_up, back, "easeOut"),
        _kf(object_id, prop, start_frame + wind_up + action, target, "easeIn"),
    ]


def overshoot(
    object_id: str,
    prop: int,
    *,
    start: float,
    target: float,
    start_frame: int = 0,
    duration: int = 20,
    settle: int = 10,
    amount: float = 0.12,
) -> list[Keyframe]:
    """Pass the target, then settle back onto it.

    Physical objects have momentum, so they arrive slightly past where they are
    going and return. `amount` is the overshoot as a fraction of travel; 0.08-0.15
    reads as weight, more reads as a bounce.
    """
    past = target + (target - start) * amount
    return [
        _kf(object_id, prop, start_frame, start, "easeIn"),
        _kf(object_id, prop, start_frame + duration, past, "easeOut"),
        _kf(object_id, prop, start_frame + duration + settle, target, "easeInOut"),
    ]


def follow_through(
    leader_frames: list[Keyframe],
    follower_id: str,
    *,
    delay: int = 5,
    damping: float = 0.75,
) -> list[Keyframe]:
    """Derive a trailing copy of a motion for a subordinate part.

    A dragged element arrives late and travels less far. `delay` is the lag in
    frames; `damping` scales the excursion from the first value.

    This takes an existing motion rather than parameters, so a follower cannot
    drift out of sync with its leader when the leader is retimed.
    """
    if not leader_frames:
        return []
    base = leader_frames[0]["value"]
    return [
        {
            **kf,
            "objectId": follower_id,
            "frame": kf["frame"] + delay,
            "value": round(base + (kf["value"] - base) * damping, 3),
        }
        for kf in leader_frames
    ]


def parallax_factor(depth: float) -> float:
    """How much a layer moves relative to the camera, from its depth.

    depth 0 = the focal plane, moving 1:1 with the camera.
    depth 1 = infinitely far, effectively static.
    depth < 0 = nearer than focus, moving MORE than the camera — which is what
    sells a foreground element sweeping past.
    """
    return 1.0 - depth


def parallax_shift(
    layers: list[tuple[str, float]],
    prop: int,
    *,
    camera_delta: float,
    start_frame: int,
    end_frame: int,
    base_value: float = 0.0,
    easing: str = "cinematic",
) -> list[Keyframe]:
    """Offset layers against a camera move, by depth.

    Depth is *rate*: far things move less. Applying one transform to a whole
    scene produces a flat slide; this is what turns the same camera move into
    space.

    `camera_delta` is how far the camera travelled, in scene units. Each layer
    moves by `camera_delta * parallax_factor(depth)` in the opposite direction.
    """
    out: list[Keyframe] = []
    for oid, depth in layers:
        shift = -camera_delta * parallax_factor(depth)
        out.append(_kf(oid, prop, start_frame, base_value, easing))
        out.append(_kf(oid, prop, end_frame, base_value + shift, easing))
    return out


def breathe(
    object_id: str,
    prop: int,
    *,
    center: float,
    amplitude: float,
    period: int = 90,
    cycles: int = 2,
    start_frame: int = 0,
    phase: float = 0.0,
) -> list[Keyframe]:
    """A slow oscillation — idle life for something that would otherwise be dead still.

    `phase` (0-1) shifts the cycle. Giving sibling elements different phases is
    what stops a group of breathing objects from pulsing in unison, which reads
    as a strobe rather than as life.
    """
    out: list[Keyframe] = []
    offset = int(period * phase)
    for c in range(cycles):
        base = start_frame + c * period + offset
        out.append(_kf(object_id, prop, base, center, "easeInOut"))
        out.append(_kf(object_id, prop, base + period // 2, center + amplitude, "easeInOut"))
    out.append(_kf(object_id, prop, start_frame + cycles * period + offset, center, "easeInOut"))
    return out
