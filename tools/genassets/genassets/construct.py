"""Build vector art from primitives, and shade it geometrically.

Why this is the primary path, not the fallback
----------------------------------------------
The pipeline's original route was: ask an image model for a picture, quantise
it, trace the raster back to vectors. That route loses on every axis it is
measured on. Colour count is whatever the quantiser lands on (the one asset
that met the quality bar came back with 84 near-duplicate colours against a
24-36 target). Vertices sit where pixels happened to change, not where the
bends are, so a bone rig tears the art. And it costs money per attempt.

Constructing the art instead inverts all three. The colour count is chosen, so
it is correct by definition. Vertices are emitted where the joints are, because
the recipe knows where the joints are. And it costs nothing, which is what makes
it a real answer to a depleted API rather than a consolation prize.

This is also how drawing is actually taught: pass 2 of `animation-craft` is
"what is it made of?" — primitives with cross-contours. The tracing route skips
straight to pass 4 and that is precisely why its output reads as generated.

Shading is geometry, not prompting
----------------------------------
`facet.py` established the principle on folds: a crease is the consequence of a
fold, and a fold is geometry, so derive it rather than asking for it. The same
holds for form shading. A rounded form under a directional light has bands of
tone running perpendicular to the light. That is computable — project every
vertex onto the light direction and cut at fractions of the extent.

So `shade_form` produces the four tonal steps the house standard demands
(base, shadow, halftone, highlight) plus a rim, from one closed outline and one
light vector. No model is asked for "layered tones" and no quantiser has to
find them.

Coordinates
-----------
SVG/Rive convention: **y increases downward**. A light from the upper-front-left
therefore travels down and to the right, `direction = (+0.707, +0.707)`. Getting
this backwards lights the form from below, which reads as horror-movie
uplighting — the single most common error when porting maths-convention code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from .facet import Point, commands_from_polygon, polygon_from_commands, split_polygon

__all__ = [
    "KAPPA", "Palette", "PALETTES", "Light", "KEY_UPPER_LEFT",
    "ellipse", "capsule", "tapered", "wedge", "polygon",
    "transform", "band_polygon", "crescent", "shade_form", "contact_shadow", "tint",
    "DEFAULT_BANDS", "RIM_BAND", "Form",
]

#: Circle-to-cubic-bezier constant: 4/3 * tan(pi/8). Four cubics with control
#: points at this fraction of the radius approximate a circle to within 0.02%.
KAPPA = 0.5522847498307936


# --- palette --------------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    """A complete lighting set for one mood.

    Six roles, because four tonal steps plus a bounce and a rim is what the
    house standard requires and what a directional light actually produces.
    Values are `#rrggbb`; alpha is added at emit time since Rive wants
    `#aarrggbb` with alpha first.

    Taken from the mood table in the `animation-craft` skill, which sources them
    to Gurney's *Color and Light*, the ASC lighting-ratio convention and NOAA's
    underwater attenuation figures.
    """

    name: str
    key: str
    mid: str
    shadow: str
    bounce: str
    rim: str
    accent: str

    def as_list(self) -> list[str]:
        return [self.key, self.mid, self.shadow, self.bounce, self.rim, self.accent]


#: Cited mood palettes. A generated asset picks one and commits to it — mixing
#: two is what produces the muddy "AI look" the owner rejected.
PALETTES: dict[str, Palette] = {
    p.name: p for p in (
        Palette("warm-optimism", "#FFD18A", "#C9825A", "#3B2944", "#B9E6C3", "#FFF0C2", "#F06A3A"),
        Palette("melancholy",    "#B9C8D8", "#65758A", "#202B3D", "#718BA8", "#DCE7F2", "#A98BAE"),
        Palette("dread",         "#667A8C", "#354254", "#070B14", "#243348", "#B8D5E6", "#8B2635"),
        Palette("wonder",        "#8ED8E8", "#5E79B8", "#111B46", "#385B91", "#FFF1B8", "#F4C95D"),
        Palette("tropical-daylight", "#FFF3B0", "#F0A36B", "#14505A", "#49C7B1", "#FFFFFF", "#FF6F61"),
        Palette("underwater-shallow", "#8BE3E0", "#2F9F9B", "#064B67", "#1B9AAA", "#D7FFFF", "#F36C4A"),
        Palette("underwater-deep",    "#2C6996", "#174A72", "#020A1A", "#123B68", "#74B8D8", "#7AD7D0"),
        Palette("sunset",        "#FFB347", "#B85B45", "#2B1E3A", "#6A3B62", "#FFD98A", "#E85D3F"),
        Palette("moonlight",     "#ACACC1", "#5151B0", "#060660", "#506886", "#F2F5FF", "#C9D6E8"),
        Palette("clinical",      "#F4F7F8", "#AAB7BF", "#33404A", "#C9D1D8", "#FFFFFF", "#4C9FB8"),
    )
}


@dataclass(frozen=True)
class Light:
    """A directional key light.

    `direction` is the way photons travel, FROM the light TOWARD the subject, in
    screen coordinates where y increases downward. A vertex with a low projection
    onto this vector faces the light and is bright.
    """

    dx: float
    dy: float

    @property
    def unit(self) -> tuple[float, float]:
        m = math.hypot(self.dx, self.dy) or 1.0
        return self.dx / m, self.dy / m

    @property
    def cut_angle(self) -> float:
        """Angle for `facet.split_polygon` whose normal is the light direction.

        `_side` there measures along `(-sin a, cos a)`, so solving that against
        the light unit vector gives `a = atan2(-dx, dy)`.
        """
        dx, dy = self.unit
        return math.atan2(-dx, dy)


#: The house key light: upper-front-left, so it travels down and to the right.
#: Every REQUIRED_CLAUSE in `standard.py` names this direction, so the geometry
#: and the prompt agree rather than lighting the same subject two ways.
KEY_UPPER_LEFT = Light(0.7071, 0.7071)


# --- primitives -----------------------------------------------------------

def ellipse(cx: float, cy: float, rx: float, ry: float, *, segments: int = 4) -> list[dict]:
    """A closed ellipse as cubic bezier commands.

    Four segments is the standard circle approximation and is what a human would
    draw. More segments are available because a form that will be BENT needs
    vertices where the bend falls — the craft note is that vertex placement is a
    rigging decision made at draw time, and a 4-point oval never deforms well.
    """
    if segments < 3:
        raise ValueError(f"an ellipse needs at least 3 segments, got {segments}")
    step = 2 * math.pi / segments
    # Handle length for an arc of `step` radians, exact for step = pi/2.
    k = 4 / 3 * math.tan(step / 4)

    pts = [(cx + rx * math.cos(i * step), cy + ry * math.sin(i * step)) for i in range(segments)]
    tans = [(-rx * math.sin(i * step) * k, ry * math.cos(i * step) * k) for i in range(segments)]

    cmds: list[dict] = [{"commandType": "moveTo", "x": pts[0][0], "y": pts[0][1]}]
    for i in range(segments):
        j = (i + 1) % segments
        cmds.append({
            "commandType": "cubicTo",
            "outX": pts[i][0] + tans[i][0], "outY": pts[i][1] + tans[i][1],
            "inX": pts[j][0] - tans[j][0], "inY": pts[j][1] - tans[j][1],
            "endX": pts[j][0], "endY": pts[j][1],
        })
    cmds.append({"commandType": "close"})
    return cmds


def tapered(x1: float, y1: float, x2: float, y2: float,
            w1: float, w2: float, *, round_end: bool = True) -> list[dict]:
    """A limb: a quad from `(x1,y1)` width `w1` to `(x2,y2)` width `w2`.

    The workhorse primitive for flippers, legs, tails and fins. Taper is what
    separates a limb from a sausage — the craft rule is that one side of a form
    should be straighter than the other, and equal widths at both ends make both
    sides identical.

    `round_end` caps the narrow end with a curve, which every organic limb has
    and no rectangle does.
    """
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        raise ValueError("a tapered form needs two distinct endpoints")
    # Unit normal to the spine.
    nx, ny = -dy / length, dx / length
    h1, h2 = w1 / 2, w2 / 2

    a = (x1 + nx * h1, y1 + ny * h1)
    b = (x2 + nx * h2, y2 + ny * h2)
    c = (x2 - nx * h2, y2 - ny * h2)
    d = (x1 - nx * h1, y1 - ny * h1)

    cmds: list[dict] = [{"commandType": "moveTo", "x": a[0], "y": a[1]},
                        {"commandType": "lineTo", "x": b[0], "y": b[1]}]
    if round_end:
        # Bulge past the tip by the end half-width, so the cap is a semicircle.
        ux, uy = dx / length, dy / length
        k = h2 * KAPPA * 1.3333
        cmds.append({
            "commandType": "cubicTo",
            "outX": b[0] + ux * k, "outY": b[1] + uy * k,
            "inX": c[0] + ux * k, "inY": c[1] + uy * k,
            "endX": c[0], "endY": c[1],
        })
    else:
        cmds.append({"commandType": "lineTo", "x": c[0], "y": c[1]})
    cmds.append({"commandType": "lineTo", "x": d[0], "y": d[1]})
    cmds.append({"commandType": "close"})
    return cmds


def capsule(x1: float, y1: float, x2: float, y2: float, r: float) -> list[dict]:
    """A rounded-end bar. A tapered form with equal ends and both caps round."""
    return tapered(x1, y1, x2, y2, r * 2, r * 2, round_end=True)


def wedge(apex: Point, base_a: Point, base_b: Point, *, round_base: float = 0.0) -> list[dict]:
    """A triangle, optionally with a bowed base.

    Heads, fins, beaks and dorsal fins. `round_base` bows the base outward as a
    fraction of its length — a straight base reads as a signpost.
    """
    cmds: list[dict] = [{"commandType": "moveTo", "x": apex[0], "y": apex[1]},
                        {"commandType": "lineTo", "x": base_a[0], "y": base_a[1]}]
    if round_base:
        mx, my = (base_a[0] + base_b[0]) / 2, (base_a[1] + base_b[1]) / 2
        ax, ay = mx - apex[0], my - apex[1]
        m = math.hypot(ax, ay) or 1.0
        bulge = math.hypot(base_b[0] - base_a[0], base_b[1] - base_a[1]) * round_base
        cx, cy = mx + ax / m * bulge, my + ay / m * bulge
        cmds.append({
            "commandType": "cubicTo",
            "outX": base_a[0] + (cx - base_a[0]) * 0.55, "outY": base_a[1] + (cy - base_a[1]) * 0.55,
            "inX": base_b[0] + (cx - base_b[0]) * 0.55, "inY": base_b[1] + (cy - base_b[1]) * 0.55,
            "endX": base_b[0], "endY": base_b[1],
        })
    else:
        cmds.append({"commandType": "lineTo", "x": base_b[0], "y": base_b[1]})
    cmds.append({"commandType": "close"})
    return cmds


def polygon(points: Sequence[Point]) -> list[dict]:
    """A closed straight-sided form."""
    return commands_from_polygon(list(points))


def transform(cmds: Iterable[dict], *, dx: float = 0.0, dy: float = 0.0,
              scale: float = 1.0, rotate: float = 0.0,
              about: Point = (0.0, 0.0)) -> list[dict]:
    """Rotate, scale and translate a command list about a pivot.

    Recipes are written in a canonical pose and placed afterwards, so the
    proportions in a recipe stay readable as ratios rather than being
    pre-multiplied into absolute coordinates.
    """
    t = math.radians(rotate)
    cos_t, sin_t = math.cos(t), math.sin(t)
    ox, oy = about

    def move(x: float, y: float) -> tuple[float, float]:
        x, y = (x - ox) * scale, (y - oy) * scale
        return ox + x * cos_t - y * sin_t + dx, oy + x * sin_t + y * cos_t + dy

    out: list[dict] = []
    for c in cmds:
        c = dict(c)
        for xk, yk in (("x", "y"), ("outX", "outY"), ("inX", "inY"), ("endX", "endY")):
            if xk in c:
                c[xk], c[yk] = move(c[xk], c[yk])
        out.append(c)
    return out


# --- shading --------------------------------------------------------------

#: Cut points along the light axis, as fractions of the form's extent.
#: Derived from the Notan 60/30/10 split and the 5-10% highlight budget in the
#: craft skill: a narrow highlight, a broad key, a mid, then the shadow.
DEFAULT_BANDS = (0.10, 0.52, 0.80)

#: Where the rim sits — the far sliver, away from the key. Rim light comes from
#: behind, so it appears on the edge the key does not reach.
RIM_BAND = 0.94


def band_polygon(points: list[Point], light: Light,
                 cuts: Sequence[float] = DEFAULT_BANDS) -> list[list[Point]]:
    """Slice a closed form into tonal bands perpendicular to the light.

    Each cut is a fraction of the form's extent along the light direction, so
    the bands scale with the form and a recipe does not carry pixel offsets.

    Bands are returned lit-first. Any that come back with fewer than three
    points are dropped: a band narrower than the form's own curvature is a
    zero-area sliver, and emitting it would be an invisible shape and a silent
    bug — the same failure `facet.facet_shapes` guards against.
    """
    if not points:
        return []
    ux, uy = light.unit
    projections = [p[0] * ux + p[1] * uy for p in points]
    lo, hi = min(projections), max(projections)
    span = hi - lo
    if span < 1e-9:
        return [points]

    angle = light.cut_angle
    bands: list[list[Point]] = []
    remaining = points
    for cut in cuts:
        t = lo + span * cut
        origin = (ux * t, uy * t)
        far, near = split_polygon(remaining, origin, angle)
        if len(near) >= 3:
            bands.append(near)
        if len(far) < 3:
            remaining = []
            break
        remaining = far
    if len(remaining) >= 3:
        bands.append(remaining)
    return bands


def crescent(points: list[Point], light: Light, *, inset: float = 0.34,
             coverage: float = 0.42, toward_light: bool = False) -> list[Point]:
    """The shadow (or highlight) region of a rounded form, with a CURVED edge.

    Straight-line banding was the first attempt and it is wrong for anything
    organic. Cutting a form with a chord gives every facet a hard straight edge,
    so a shaded ellipse reads as bevelled glass and a cluster of them reads as a
    heap of eggs. That was visible the moment the first turtle was rendered.

    A real terminator follows the form. The construction here is the one vector
    artists actually use: the shadow's OUTER boundary is the form's own outline,
    and its INNER boundary is a smaller copy of that same outline pushed toward
    the light. Both edges are therefore curved, and curved in sympathy, which is
    what makes a sphere read as a sphere rather than a polygon.

    `coverage` is the fraction of the outline the region spans — 0.42 puts the
    terminator slightly past the halfway point, where a light at 45 degrees puts
    it. `inset` is how far the inner edge sits in, as a fraction of the form's
    radius; larger means a thinner crescent.
    """
    n = len(points)
    if n < 3:
        return []
    ux, uy = light.unit
    if toward_light:
        ux, uy = -ux, -uy

    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    # Order the outline by how much each vertex faces away from the light, so
    # the region is centred on the darkest point rather than on a fixed vertex.
    proj = [((p[0] - cx) * ux + (p[1] - cy) * uy, i) for i, p in enumerate(points)]
    darkest = max(proj)[1]

    span = max(3, int(round(n * coverage)))
    half = span // 2
    idx = [(darkest - half + k) % n for k in range(span)]

    outer = [points[i] for i in idx]
    radius = max(math.hypot(p[0] - cx, p[1] - cy) for p in points) or 1.0
    shift = radius * inset
    # Inner edge: the same arc pulled toward the centre and nudged toward the
    # light. Pulling toward the centre is what keeps it inside the silhouette
    # at the horns of the crescent, where a pure translation would poke out.
    inner = [((p[0] - cx) * (1 - inset * 0.55) + cx - ux * shift * 0.55,
              (p[1] - cy) * (1 - inset * 0.55) + cy - uy * shift * 0.55)
             for p in reversed(outer)]
    return outer + inner


@dataclass(frozen=True)
class Form:
    """One constructed part, before shading."""

    name: str
    commands: list[dict]
    #: Which palette role the form's base tone comes from. Ignored when
    #: `local` is set.
    role: str = "key"
    #: An explicit local colour for this material, normally built with `tint`
    #: from a palette entry so the set stays harmonious.
    local: str | None = None
    #: Suppress the rim on a form that sits INSIDE another — a scute set into a
    #: shell has no lit outer edge of its own, and giving it one is what made
    #: the first turtle's scutes read as loose eggs piled on the back.
    rim: bool = True
    #: Rigid parts (a turtle's carapace, a beak, a prop) are not banded — the
    #: craft rule is bind to deform, parent to stay rigid, and a shell that
    #: shades like a soft form reads as rubber.
    shade: bool = True


def tint(base: str, *, hue: float = 0.0, sat: float = 0.0, val: float = 0.0) -> str:
    """Shift a palette colour into a distinct LOCAL colour.

    A palette supplies six lighting roles, not a materials list. Shading every
    form from the same six roles yields a creature painted in one colour with
    four tones of it — which grades out at 8 colours against a 24-36 target,
    and reads exactly as flat as the assets that were rejected.

    Real subjects have local colour: a turtle's carapace, plastron, flipper
    skin and beak are four different materials before any light touches them.
    The research puts it at 12-18 base materials for a hero.

    Shifting in HSV from a palette entry keeps the set harmonious — every local
    colour remains a relative of the key — while making it genuinely distinct.
    `hue` is in degrees; `sat` and `val` are additive fractions of full scale.
    """
    import colorsys
    h = base.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    hh = (hh + hue / 360.0) % 1.0
    ss = min(1.0, max(0.0, ss + sat))
    vv = min(1.0, max(0.0, vv + val))
    r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
    return "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b))


def _mix(a: str, b: str, t: float) -> str:
    """Blend two `#rrggbb` colours. Used to place the halftone between key and
    shadow rather than inventing a fifth colour outside the palette."""
    a, b = a.lstrip("#"), b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(f"{round(ca + (cb - ca) * t):02x}")
    return "#" + "".join(out)


def shade_form(form: Form, light: Light, palette: Palette, *,
               alpha: str = "ff") -> list[dict]:
    """Turn one outline into its tonal facets, as createShapes payloads.

    Produces the four steps the house standard requires — highlight, key,
    halftone, shadow — plus an optional rim sliver. Colours come from the
    palette rather than being computed brightness scalings, so the shadow keeps
    its hue instead of turning grey, which is rejection-checklist item 2.

    A form marked `shade=False` returns a single flat shape.
    """
    base = form.local or getattr(palette, form.role, palette.key)
    if not form.shade:
        return [{"name": form.name,
                 "paths": [{"commands": [dict(c) for c in form.commands]}],
                 "paints": [{"color": f"#{alpha}{base.lstrip('#')}"}]}]

    pts = polygon_from_commands(form.commands)
    if len(pts) < 3:
        raise ValueError(f"{form.name!r} has too few points to shade")

    # Shadow and highlight are crescents whose inner edge follows the form.
    # See `crescent` for why straight-line banding was abandoned.
    shadow_pts = crescent(pts, light, inset=0.30, coverage=0.46)
    core_pts = crescent(pts, light, inset=0.62, coverage=0.30)
    hi_pts = crescent(pts, light, inset=0.78, coverage=0.18, toward_light=True)

    # The base goes down first at full curved fidelity, and the tonal regions
    # stack ON TOP of it — layered cut-paper, exactly as the house standard's
    # REQUIRED_CLAUSES describe.
    #
    # This is not merely tidier. The regions are polygons, because bezier
    # control points cannot survive the clip, so every region edge is a chord of
    # the true curve and sits slightly inside it. Emitting regions alone would
    # leave a hairline of background along the silhouette. Painting them over an
    # intact base means that error costs a fraction of a pixel of facet
    # placement instead of a hole, and the silhouette stays the exact curve the
    # primitive drew — the thing the rejection checklist is measured against.
    out: list[dict] = [{
        "name": f"{form.name}-base",
        "paths": [{"commands": [dict(c) for c in form.commands]}],
        "paints": [{"color": f"#{alpha}{base.lstrip('#')}"}],
    }]

    # All four tones derive FROM the local colour, not from the palette
    # directly. Painting every form's highlight in one shared rim colour would
    # collapse a dozen materials onto one bright value — the flattening that
    # `local` exists to prevent, reintroduced one level down. Mixing toward the
    # palette keeps each material's hue in its own highlight while the whole set
    # still reads as one light.
    regions = [
        ("halftone", _mix(base, palette.shadow, 0.42), shadow_pts),
        ("shadow", _mix(base, palette.shadow, 0.78), core_pts),
        ("highlight", _mix(base, palette.rim, 0.34), hi_pts),
    ]
    if form.rim:
        regions.append(("rim", _mix(base, palette.rim, 0.70),
                        crescent(pts, light, inset=0.92, coverage=0.22)))

    for suffix, colour, region in regions:
        if len(region) < 3:
            continue
        out.append({
            "name": f"{form.name}-{suffix}",
            "paths": [{"commands": commands_from_polygon(region)}],
            "paints": [{"color": f"#{alpha}{colour.lstrip('#')}"}],
        })
    return out


def contact_shadow(cx: float, cy: float, width: float, *,
                   palette: Palette, opacity: float = 0.35,
                   squash: float = 0.22) -> dict:
    """The ellipse under a form that stops it floating.

    Ranked in the craft notes just behind occlusion and relative size as a depth
    cue, and it is the cheapest of the three. Defaults follow the measured
    guidance: 25-45% opacity, 0.8-1.2x the footprint width.
    """
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be 0..1, got {opacity}")
    rx = width * 0.5
    return {
        "name": "contact-shadow",
        "paths": [{"commands": ellipse(cx, cy, rx, rx * squash)}],
        "paints": [{"color": f"#{round(opacity * 255):02x}{palette.shadow.lstrip('#')}"}],
    }
