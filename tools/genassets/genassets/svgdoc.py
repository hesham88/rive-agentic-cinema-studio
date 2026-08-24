"""Parse a traced SVG document into Rive-ready shape definitions.

`rivepath.py` converts one `d` string. This module handles the whole document:
pulls out each `<path>` with its fill and transform, drops the background plate a
tracer emits, normalizes colors to Rive's `#aarrggbb`, and fits everything to a
target artboard.

Output is exactly the `shapes` payload `path_editor.createShapes` expects.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .rivepath import parse_path, svg_color_to_rive

__all__ = ["SvgShape", "parse_svg_document", "to_create_shapes_payload"]

_PATH_RE = re.compile(r"<path\b([^>]*)/?>", re.S)
_ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')
_VIEWBOX_RE = re.compile(r'viewBox\s*=\s*"([^"]*)"')
_WH_RE = re.compile(r'\b(width|height)\s*=\s*"([\d.]+)')
_TRANSLATE_RE = re.compile(r"translate\(\s*([-\d.eE]+)[ ,]+([-\d.eE]+)\s*\)")


@dataclass
class SvgShape:
    name: str
    commands: list[dict]
    fill: str
    # Bounds in source-SVG units, before fitting.
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def _bounds(commands: list[dict]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for c in commands:
        t = c["commandType"]
        if t in ("moveTo", "lineTo"):
            xs.append(c["x"]); ys.append(c["y"])
        elif t == "cubicTo":
            xs += [c["control1X"], c["control2X"], c["endX"]]
            ys += [c["control1Y"], c["control2Y"], c["endY"]]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _translate(commands: list[dict], dx: float, dy: float) -> None:
    for c in commands:
        t = c["commandType"]
        if t in ("moveTo", "lineTo"):
            c["x"] += dx; c["y"] += dy
        elif t == "cubicTo":
            c["control1X"] += dx; c["control1Y"] += dy
            c["control2X"] += dx; c["control2Y"] += dy
            c["endX"] += dx; c["endY"] += dy


def _scale(commands: list[dict], s: float) -> None:
    for c in commands:
        t = c["commandType"]
        if t in ("moveTo", "lineTo"):
            c["x"] *= s; c["y"] *= s
        elif t == "cubicTo":
            for k in ("control1X", "control1Y", "control2X", "control2Y", "endX", "endY"):
                c[k] *= s


def parse_svg_document(
    svg_text: str,
    *,
    drop_background: bool = True,
    max_commands_per_path: int | None = 4000,
) -> list[SvgShape]:
    """Extract every `<path>` as an SvgShape, in document order.

    drop_background: tracers emit a full-canvas rectangle as the first path (the
        page behind the art). Keeping it makes the imported artwork a solid block,
        so it is dropped by default — detected by area rather than by index, since
        not every tracer puts it first.
    """
    shapes: list[SvgShape] = []
    for i, raw_attrs in enumerate(_PATH_RE.findall(svg_text)):
        attrs = dict(_ATTR_RE.findall(raw_attrs))
        d = attrs.get("d", "").strip()
        if not d:
            continue

        commands = parse_path(d, max_commands=max_commands_per_path)
        if not commands:
            continue

        # A tracer emits `transform="translate(x,y)"`; fold it into the geometry
        # so Rive receives absolute coordinates.
        if (m := _TRANSLATE_RE.search(attrs.get("transform", ""))):
            _translate(commands, float(m.group(1)), float(m.group(2)))

        try:
            fill = svg_color_to_rive(attrs.get("fill", "#000000"))
        except ValueError:
            fill = "#ff000000"

        x0, y0, x1, y1 = _bounds(commands)
        shapes.append(
            SvgShape(name=attrs.get("id") or f"path{i + 1}", commands=commands,
                     fill=fill, min_x=x0, min_y=y0, max_x=x1, max_y=y1)
        )

    if drop_background and len(shapes) > 1:
        doc_w, doc_h = _document_size(svg_text)
        if doc_w and doc_h:
            plate = doc_w * doc_h * 0.92
            shapes = [
                s for s in shapes
                if (s.max_x - s.min_x) * (s.max_y - s.min_y) < plate
            ] or shapes

    return shapes


def _document_size(svg_text: str) -> tuple[float, float]:
    if (m := _VIEWBOX_RE.search(svg_text)):
        parts = [float(v) for v in re.split(r"[ ,]+", m.group(1).strip())]
        if len(parts) == 4:
            return parts[2], parts[3]
    dims = dict(_WH_RE.findall(svg_text))
    return float(dims.get("width", 0)), float(dims.get("height", 0))


@dataclass(frozen=True)
class MotionEnvelope:
    """How far the art will travel once it is animated.

    The artboard clips. A mark fitted edge-to-edge has nowhere to go, so the
    first keyframe that moves it slices pieces off — which is exactly what
    shipped: a plane that lost a wingtip every time it banked.

    The old fix was a flat 6% margin, which is a guess that knows nothing about
    the animation. This makes the caller declare the motion instead, and derives
    the margin from it. Declaring `rotation=25` reserves the room a 25-degree
    rotation actually needs; declaring nothing reserves almost none, because a
    static mark should fill its frame.

    All fractions are of the artboard's own dimension, so an envelope is
    resolution-independent.
    """

    #: Peak translation away from centre, as a fraction of the artboard.
    drift_x: float = 0.0
    drift_y: float = 0.0
    #: Peak scale multiplier. 1.15 means the art grows 15% at its largest.
    scale: float = 1.0
    #: Peak absolute rotation in degrees, either direction.
    rotation: float = 0.0
    #: Extra breathing room so nothing kisses the edge. A form that touches the
    #: frame reads as cropped even when every pixel is technically inside.
    bleed: float = 0.02

    def rotation_factor(self) -> float:
        """How much a rotation grows a bounding box.

        A box rotated by theta has half-extent (w|cos| + h|sin|)/2. Treating the
        art as square is the conservative case and peaks at sqrt(2) near 45
        degrees, which is the number to reserve for anything that tumbles.
        """
        t = math.radians(abs(self.rotation))
        return abs(math.cos(t)) + abs(math.sin(t))

    def margin(self) -> float:
        """The fraction of each edge to leave empty.

        Solves for the largest art that still fits after the worst frame:

            (f/2) * rotation * scale + drift  <=  0.5 - bleed

        where f is the fraction of the artboard the resting art occupies.
        """
        drift = max(abs(self.drift_x), abs(self.drift_y))
        room = 0.5 - self.bleed - drift
        growth = max(self.rotation_factor() * max(self.scale, 1e-6), 1e-6)
        if room <= 0:
            # The drift alone overruns the frame. Shrink to the floor and let
            # the caller see a tiny mark rather than a silently cropped one.
            return 0.45
        f = min(2.0 * room / growth, 1.0)
        return max(0.0, min(0.45, (1.0 - f) / 2.0))


#: Sensible envelopes for the motion this pipeline actually emits.
ENVELOPES = {
    # A hero that glides along an arc and banks into it.
    "hero-glide": MotionEnvelope(drift_x=0.10, drift_y=0.06, scale=1.06, rotation=18),
    # A creature swimming or flying in place — undulation, no travel.
    "swim-cycle": MotionEnvelope(drift_x=0.04, drift_y=0.05, scale=1.04, rotation=10),
    # A widget that presses, hovers and settles.
    "ui-widget": MotionEnvelope(drift_x=0.01, drift_y=0.02, scale=1.08, rotation=0),
    # Anything that tumbles end over end.
    "tumble": MotionEnvelope(rotation=45, scale=1.05),
    # A mark that never moves.
    "static": MotionEnvelope(bleed=0.04),
}


def to_create_shapes_payload(
    shapes: list[SvgShape],
    *,
    artboard_width: float,
    artboard_height: float,
    margin: float | None = None,
    envelope: "MotionEnvelope | str | None" = None,
    shared_origin: bool = False,
) -> list[dict]:
    """Fit shapes to the artboard and emit the createShapes payload.

    Rive path commands are in the shape's OWN local space around (0,0), while the
    shape's x/y position it in the parent. So each shape is centred on its own
    origin and then placed — matching the coordinate system the tool documents.

    shared_origin: give EVERY shape the same x/y (the artwork's centre) and bake
        each shape's offset into its path commands instead. Rive rotates and
        scales a shape about its own origin, so four shapes with four origins
        rotating 10 degrees each tear the artwork apart. With one shared origin,
        an identical transform keyframe on each shape moves them as a rigid body.
        Use this whenever the shapes will be animated together.

    envelope: how far the art will move once animated, as a `MotionEnvelope` or
        a key of `ENVELOPES`. The margin is derived from it, so art that banks
        18 degrees is drawn small enough to still be whole at 18 degrees. Pass
        an explicit `margin` only to override that reasoning.

        Defaults to "static". A caller that animates without declaring an
        envelope gets the old behaviour, so the failure is visible rather than
        silent — but every animating caller in this pipeline should name one.
    """
    if not shapes:
        return []

    if margin is None:
        env = envelope if envelope is not None else "static"
        if isinstance(env, str):
            try:
                env = ENVELOPES[env]
            except KeyError:
                raise ValueError(
                    f"unknown envelope {env!r}; expected one of "
                    f"{sorted(ENVELOPES)} or a MotionEnvelope"
                ) from None
        margin = env.margin()

    min_x = min(s.min_x for s in shapes)
    min_y = min(s.min_y for s in shapes)
    max_x = max(s.max_x for s in shapes)
    max_y = max(s.max_y for s in shapes)
    src_w = max(max_x - min_x, 1e-6)
    src_h = max(max_y - min_y, 1e-6)

    usable_w = artboard_width * (1 - 2 * margin)
    usable_h = artboard_height * (1 - 2 * margin)
    scale = min(usable_w / src_w, usable_h / src_h)

    # Where the fitted artwork's top-left lands on the artboard.
    off_x = (artboard_width - src_w * scale) / 2
    off_y = (artboard_height - src_h * scale) / 2

    # The artwork's centre on the artboard — the shared pivot.
    pivot_x = off_x + src_w * scale / 2
    pivot_y = off_y + src_h * scale / 2

    payload: list[dict] = []
    for s in shapes:
        cmds = [dict(c) for c in s.commands]
        # Source space -> origin -> scaled.
        _translate(cmds, -min_x, -min_y)
        _scale(cmds, scale)

        if shared_origin:
            # Bake the offset into the geometry; every shape sits on the pivot.
            _translate(cmds, -src_w * scale / 2, -src_h * scale / 2)
            cx, cy = pivot_x - off_x, pivot_y - off_y
        else:
            # Centre the geometry on the shape's own origin.
            cx = (s.min_x - min_x + (s.max_x - s.min_x) / 2) * scale
            cy = (s.min_y - min_y + (s.max_y - s.min_y) / 2) * scale
            _translate(cmds, -cx, -cy)

        payload.append({
            "name": s.name,
            "x": off_x + cx,
            "y": off_y + cy,
            "paths": [{"name": f"{s.name}-path", "commands": cmds}],
            "paints": [{"paintType": "fill", "color": s.fill}],
        })
    return payload


def simplify_commands(commands: list[dict], tolerance: float = 0.8) -> list[dict]:
    """Drop near-collinear vertices from a polyline (Ramer-Douglas-Peucker).

    A tracer emits a vertex per pixel-step along an edge, so a straight edge
    arrives as dozens of points. That is noise: it bloats the payload and makes
    the shape unpleasant to edit in Rive, where every vertex is a handle. Only
    line runs are simplified; cubics are preserved untouched.
    """
    if len(commands) < 3:
        return commands

    def rdp(pts: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
        if len(pts) < 3:
            return pts
        x0, y0 = pts[0]
        x1, y1 = pts[-1]
        dx, dy = x1 - x0, y1 - y0
        den = (dx * dx + dy * dy) ** 0.5
        worst, idx = 0.0, 0
        for i in range(1, len(pts) - 1):
            px, py = pts[i]
            d = (abs(dy * px - dx * py + x1 * y0 - y1 * x0) / den) if den else (
                ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5)
            if d > worst:
                worst, idx = d, i
        if worst <= eps:
            return [pts[0], pts[-1]]
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)

    out: list[dict] = []
    run: list[tuple[float, float]] = []

    def flush() -> None:
        if not run:
            return
        kept = rdp(run, tolerance)
        for x, y in kept[1:]:
            out.append({"commandType": "lineTo", "x": x, "y": y})
        run.clear()

    for c in commands:
        t = c["commandType"]
        if t == "moveTo":
            flush()
            out.append(c)
            run.append((c["x"], c["y"]))
        elif t == "lineTo":
            if run:
                run.append((c["x"], c["y"]))
            else:
                out.append(c)
                run.append((c["x"], c["y"]))
        else:
            flush()
            out.append(c)
            if t == "cubicTo":
                run.append((c["endX"], c["endY"]))
    flush()
    return out
