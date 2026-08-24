"""Split a traced silhouette into shaded facets.

Why this exists
---------------
The generate step returns a clean outline but will not reliably separate a
folded form into distinct tones. Two prompt revisions asking for "four clearly
separate flat facets, each a different shade" both came back as one flat shape,
and the vectoriser reported it exactly: 2 paths, 2 colours.

That is a real limit of prompting, not a prompt that needed more adjectives. A
paper plane's facets are not a rendering choice — they are the consequence of a
fold, and a fold is geometry. So the pipeline derives them instead of asking.

The approach: find the silhouette's dominant axis, place a fold line along it,
split every edge that crosses that line, and shade the two halves apart. That
turns one path into a form with a readable crease, which is the whole point of
the third dimension in a flat mark.

Pure geometry — no Rive, no network, no image work — so it is unit-testable and
usable by both the MCP authoring path and the byte encoder.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

__all__ = [
    "Point",
    "polygon_from_commands",
    "commands_from_polygon",
    "centroid",
    "dominant_axis",
    "split_polygon",
    "shade",
    "facet_shapes",
]

Point = tuple[float, float]


def polygon_from_commands(commands: Iterable[dict[str, Any]]) -> list[Point]:
    """Read a Rive command list as a polygon.

    Curve control points are dropped — only endpoints survive. Folding is a
    coarse operation on the overall form, and a bezier's control points do not
    move the crease anywhere useful.
    """
    pts: list[Point] = []
    for c in commands:
        kind = c.get("commandType")
        if kind in ("moveTo", "lineTo"):
            pts.append((float(c["x"]), float(c["y"])))
        elif kind == "cubicTo":
            pts.append((float(c["endX"]), float(c["endY"])))
    return pts


def commands_from_polygon(points: list[Point]) -> list[dict[str, Any]]:
    """Write a polygon back as Rive commands, closed."""
    if len(points) < 3:
        raise ValueError(f"a face needs at least 3 points, got {len(points)}")
    out: list[dict[str, Any]] = [
        {"commandType": "moveTo", "x": points[0][0], "y": points[0][1]}
    ]
    for x, y in points[1:]:
        out.append({"commandType": "lineTo", "x": x, "y": y})
    out.append({"commandType": "close"})
    return out


def centroid(points: list[Point]) -> Point:
    """Area-weighted centroid, falling back to the mean for degenerate input.

    The vertex mean is wrong for a shape whose vertices bunch at one end — a
    plane's nose has several points close together — and a fold placed at the
    vertex mean sits noticeably off the visual middle.
    """
    n = len(points)
    if n < 3:
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)

    a2 = cx = cy = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a2) < 1e-9:  # collinear
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
    return (cx / (3 * a2), cy / (3 * a2))


def dominant_axis(points: list[Point]) -> float:
    """Angle in radians of the shape's long axis.

    The first principal component of the vertices — the direction the form
    actually extends. For a paper plane that is nose-to-tail, which is exactly
    where the central fold belongs.
    """
    cx, cy = centroid(points)
    sxx = syy = sxy = 0.0
    for x, y in points:
        dx, dy = x - cx, y - cy
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    # Principal axis of the 2x2 covariance matrix.
    return 0.5 * math.atan2(2 * sxy, sxx - syy)


def _side(p: Point, origin: Point, angle: float) -> float:
    """Signed distance from the fold line. Sign picks the face."""
    nx, ny = -math.sin(angle), math.cos(angle)
    return (p[0] - origin[0]) * nx + (p[1] - origin[1]) * ny


def split_polygon(
    points: list[Point],
    origin: Point,
    angle: float,
) -> tuple[list[Point], list[Point]]:
    """Cut a polygon along a line, returning both faces.

    Sutherland–Hodgman, run twice with the half-plane inverted. Edges crossing
    the line are split at the intersection so both faces share the crease
    exactly — a seam of even a fraction of a pixel shows as a hairline against
    a dark ground.
    """
    def clip(keep_positive: bool) -> list[Point]:
        out: list[Point] = []
        n = len(points)
        for i in range(n):
            cur, nxt = points[i], points[(i + 1) % n]
            dc, dn = _side(cur, origin, angle), _side(nxt, origin, angle)
            if not keep_positive:
                dc, dn = -dc, -dn
            cur_in, nxt_in = dc >= 0, dn >= 0
            if cur_in:
                out.append(cur)
            if cur_in != nxt_in and abs(dc - dn) > 1e-12:
                t = dc / (dc - dn)
                out.append((cur[0] + t * (nxt[0] - cur[0]),
                            cur[1] + t * (nxt[1] - cur[1])))
        return out

    return clip(True), clip(False)


def shade(hex_color: str, factor: float) -> str:
    """Scale a `#aarrggbb` colour's brightness, preserving alpha.

    `factor` below 1 darkens, above 1 lightens. Applied per channel and clamped,
    so a light already near white lightens toward white rather than clipping to
    a different hue.
    """
    h = hex_color.lstrip("#")
    if len(h) == 8:
        a, rgb = h[:2], h[2:]
    elif len(h) == 6:
        a, rgb = "ff", h
    else:
        raise ValueError(f"expected #aarrggbb or #rrggbb, got {hex_color!r}")
    ch = [int(rgb[i:i + 2], 16) for i in (0, 2, 4)]
    ch = [max(0, min(255, round(v * factor))) for v in ch]
    return "#" + a + "".join(f"{v:02x}" for v in ch)


@dataclass(frozen=True)
class Facet:
    """One face of a folded form."""

    name: str
    points: list[Point]
    color: str


def facet_shapes(
    shape: dict[str, Any],
    *,
    shades: tuple[float, float] = (1.18, 0.72),
    offset: float = 0.0,
) -> list[dict[str, Any]]:
    """Turn one traced shape into two shaded faces sharing a crease.

    `shades` is (near, far): the face toward the light is brightened and the one
    away from it darkened. The default spread is deliberately wide — a fold
    separated by 10% reads as a rendering artefact, while 1.18 against 0.72 reads
    as two planes at different angles.

    `offset` slides the fold off the centroid, as a fraction of the shape's
    extent. A paper plane's spine is not its area centre.

    Returns createShapes payloads, so the result drops straight into the same
    MCP call the unfolded shape used.
    """
    paths = shape.get("paths") or []
    if not paths:
        raise ValueError("shape has no paths to fold")

    pts = polygon_from_commands(paths[0].get("commands") or [])
    if len(pts) < 4:
        raise ValueError(f"need at least 4 points to fold, got {len(pts)}")

    base_paint = (shape.get("paints") or [{}])[0]
    base_color = base_paint.get("color", "#ffffffff")

    origin = centroid(pts)
    angle = dominant_axis(pts)
    if offset:
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                   max(p[1] for p in pts) - min(p[1] for p in pts))
        nx, ny = -math.sin(angle), math.cos(angle)
        origin = (origin[0] + nx * span * offset, origin[1] + ny * span * offset)

    near, far = split_polygon(pts, origin, angle)
    name = shape.get("name", "shape")

    out: list[dict[str, Any]] = []
    for suffix, face, factor in (("near", near, shades[0]), ("far", far, shades[1])):
        if len(face) < 3:
            # A fold that misses the shape leaves one face empty; emitting a
            # 2-point path would be an invisible object and a silent bug.
            continue
        out.append({
            **{k: v for k, v in shape.items() if k not in ("paths", "paints", "name")},
            "name": f"{name}-{suffix}",
            "paths": [{"commands": commands_from_polygon(face)}],
            "paints": [{**base_paint, "color": shade(base_color, factor)}],
        })
    return out
