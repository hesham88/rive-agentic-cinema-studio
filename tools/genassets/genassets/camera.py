"""Camera engine — cinematic moves for a runtime that has no camera.

Rive has no camera object. A scene is a flat artboard, and the viewport is the
artboard itself. So a camera is *simulated* by transforming a container that
holds the scene: to move the camera right, you move the world left.

That inversion is the whole idea, and it is the thing that is easy to get wrong:

    camera pans  +100px right  ->  rig.x = -100
    camera zooms to 2x         ->  rig.scale = 2, and the rig must be
                                   re-centred so the zoom targets the point
                                   the camera is looking at, not the origin

This module computes those transforms as pure data — a list of keyframes ready
for `animation_editor.modifyKeyFrames`. No Rive, no I/O, so the maths is
testable on its own.

Property keys used (verified against a Rive Shape/LayoutComponent):
    x=13  y=14  rotation=15  scaleX=16  scaleY=17
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

__all__ = [
    "PROP",
    "Shot",
    "CameraRig",
    "ease",
    "pan",
    "zoom",
    "dolly",
    "shake",
    "orbit",
    "sequence_to_keyframes",
]

PROP = {"x": 13, "y": 14, "rotation": 15, "scaleX": 16, "scaleY": 17, "opacity": 18}

# Named easing curves as cubic-bezier control points, matching the editor's
# cubicParams {x1, y1, x2, y2}. These are the standard motion-design curves.
EASING: dict[str, tuple[float, float, float, float]] = {
    "linear": (0.0, 0.0, 1.0, 1.0),
    "ease": (0.25, 0.1, 0.25, 1.0),
    "easeIn": (0.42, 0.0, 1.0, 1.0),
    "easeOut": (0.0, 0.0, 0.58, 1.0),
    "easeInOut": (0.42, 0.0, 0.58, 1.0),
    # Cinematic: slow start, decisive middle, gentle settle. The default for
    # camera moves because a camera has mass — it cannot start or stop instantly.
    "cinematic": (0.65, 0.0, 0.35, 1.0),
    # Overshoot slightly then settle; good for a snap-to or a whip pan.
    "backOut": (0.34, 1.56, 0.64, 1.0),
}


def ease(name: str) -> dict:
    """Cubic params for a named curve, for a keyframe's `cubicParams`."""
    x1, y1, x2, y2 = EASING.get(name, EASING["cinematic"])
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


@dataclass(frozen=True)
class CameraState:
    """Where the camera is looking, in SCENE coordinates."""

    # The scene point at the centre of frame.
    look_x: float = 0.0
    look_y: float = 0.0
    # 1.0 = fit; 2.0 = twice as close.
    zoom: float = 1.0
    # Camera roll, degrees. Positive rolls the horizon clockwise.
    roll: float = 0.0


@dataclass
class Shot:
    """One camera move: where it ends, how long, and how it gets there."""

    name: str
    end: CameraState
    duration_frames: int
    easing: str = "cinematic"
    # Per-frame handheld jitter, in scene units. 0 = locked off.
    shake: float = 0.0
    shake_seed: int = 7


@dataclass
class CameraRig:
    """Converts camera states into rig transforms.

    `viewport_w/h` is the artboard size; `rig_id` is the object whose transform
    is animated — typically a container holding every scene element.
    """

    rig_id: str
    viewport_w: float
    viewport_h: float
    shots: list[Shot] = field(default_factory=list)
    start: CameraState = CameraState()

    def rig_transform(self, cam: CameraState) -> dict[str, float]:
        """The rig transform that puts `cam` on screen.

        The rig is positioned so the camera's look-at point lands at the centre
        of the viewport, scaled about that point. Because the rig moves opposite
        to the camera, the look-at offset is negated *after* scaling — scaling
        first and translating second is the difference between zooming toward
        the subject and zooming toward the origin.

        **Scale is emitted as a PERCENTAGE (100 = 1x), not a multiplier.**
        Rive's property API takes percent-displayed properties — scale, opacity,
        trim path, constraint strength — in the units the inspector shows. A
        zoom of 2.2 written as `2.2` is read as 2.2%, which scales the scene to
        a fortieth of its size and renders an apparently empty frame. Position
        maths still uses the raw multiplier.
        """
        cx, cy = self.viewport_w / 2.0, self.viewport_h / 2.0
        z = max(cam.zoom, 1e-6)
        return {
            "x": cx - cam.look_x * z,
            "y": cy - cam.look_y * z,
            "scaleX": z * 100.0,
            "scaleY": z * 100.0,
            "rotation": -cam.roll,
        }


def _jitter(seed: int, frame: int, amount: float) -> tuple[float, float]:
    """Deterministic per-frame shake offset.

    Seeded so a given shot always produces the same shake: an animation that
    re-renders differently each build is not reviewable.
    """
    rng = random.Random((seed * 92821) ^ (frame * 40503))
    angle = rng.random() * math.tau
    radius = rng.random() * amount
    return math.cos(angle) * radius, math.sin(angle) * radius


def sequence_to_keyframes(rig: CameraRig, *, fps: int = 60) -> list[dict]:
    """Turn a shot list into keyframes for `animation_editor.modifyKeyFrames`.

    Returns one keyframe per animated property per shot boundary, plus extra
    x/y keyframes on every frame of any shot with shake.
    """
    frames: list[dict] = []
    frame = 0
    current = rig.start

    def emit(f: int, props: dict[str, float], easing: str) -> None:
        for prop_name, value in props.items():
            frames.append({
                "objectId": rig.rig_id,
                "propertyKey": PROP[prop_name],
                "frame": f,
                "value": round(value, 3),
                "interpolationType": "cubic",
                "cubicParams": ease(easing),
            })

    emit(0, rig.rig_transform(current), "linear")

    for shot in rig.shots:
        start_frame = frame
        frame += max(1, shot.duration_frames)
        target = rig.rig_transform(shot.end)
        emit(frame, target, shot.easing)

        if shot.shake > 0:
            # Shake rides on top of the move: sample the eased path per frame
            # and add jitter, so the camera still travels while it shakes.
            base = rig.rig_transform(current)
            for f in range(start_frame + 1, frame):
                t = (f - start_frame) / max(1, shot.duration_frames)
                dx, dy = _jitter(shot.shake_seed, f, shot.shake)
                frames.append({
                    "objectId": rig.rig_id,
                    "propertyKey": PROP["x"],
                    "frame": f,
                    "value": round(base["x"] + (target["x"] - base["x"]) * t + dx, 3),
                    "interpolationType": "linear",
                })
                frames.append({
                    "objectId": rig.rig_id,
                    "propertyKey": PROP["y"],
                    "frame": f,
                    "value": round(base["y"] + (target["y"] - base["y"]) * t + dy, 3),
                    "interpolationType": "linear",
                })

        current = shot.end

    return frames


# --------------------------------------------------------------- shot builders
# Named moves, so a scene reads like a shot list rather than arithmetic.


def pan(name: str, to_x: float, to_y: float, *, frames: int = 90,
        zoom_level: float = 1.0, easing: str = "cinematic") -> Shot:
    """Move the camera to look at a new point, holding the zoom."""
    return Shot(name, CameraState(to_x, to_y, zoom_level), frames, easing)


def zoom(name: str, level: float, *, at_x: float = 0.0, at_y: float = 0.0,
         frames: int = 60, easing: str = "cinematic") -> Shot:
    """Zoom toward a point. level > 1 moves closer."""
    return Shot(name, CameraState(at_x, at_y, level), frames, easing)


def dolly(name: str, to_x: float, to_y: float, level: float, *,
          frames: int = 120, easing: str = "cinematic") -> Shot:
    """Move and zoom at once — the classic push-in on a subject."""
    return Shot(name, CameraState(to_x, to_y, level), frames, easing)


def shake(name: str, intensity: float = 6.0, *, frames: int = 30,
          at_x: float = 0.0, at_y: float = 0.0, level: float = 1.0) -> Shot:
    """Hold position while shaking — impact, engine rumble, earthquake."""
    return Shot(name, CameraState(at_x, at_y, level), frames, "linear",
                shake=intensity)


def orbit(name: str, roll_degrees: float, *, frames: int = 90,
          at_x: float = 0.0, at_y: float = 0.0, level: float = 1.0,
          easing: str = "cinematic") -> Shot:
    """Roll the camera — a canted/Dutch angle."""
    return Shot(name, CameraState(at_x, at_y, level, roll_degrees), frames, easing)
