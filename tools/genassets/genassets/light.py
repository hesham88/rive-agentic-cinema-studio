"""The light engine — 2D lights that behave like light.

Rive has no lighting model. A "light" here is vector geometry painted with a
radial or linear gradient, so the whole engine is really one question: what
should the gradient stops be so the result reads as illumination rather than as
a coloured blob?

Three things separate the two:

  * **Falloff is not linear.** Real irradiance drops with the square of
    distance. A two-stop gradient from opaque to transparent produces a flat
    disc with a hard edge; the same span with inverse-square stops produces a
    hot core that fades into nothing, which is what the eye reads as a lamp.
  * **Light has a colour temperature.** A candle is not "orange" and an
    overcast sky is not "blue" — they sit on the blackbody curve, and picking
    colours off that curve is why a warm key against a cool fill looks like
    photography instead of like two hues chosen at random.
  * **Light is never perfectly steady.** A flame's flicker is the visible part;
    a fluorescent tube's hum is another. Both are periodic, and both must be
    *reproducible* — a seeded sum of sines, not a random walk, so the same
    prompt renders the same file twice.

Everything above is pure arithmetic and lives at the top of this module, unit
tested without touching Rive. The MCP authoring below turns it into artboards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .rivemcp import RiveMCP

__all__ = [
    "kelvin_to_rgb",
    "kelvin_to_hex",
    "falloff_stops",
    "flicker",
    "three_point",
    "LightRig",
    "CANDLE_K",
    "TUNGSTEN_K",
    "DAYLIGHT_K",
    "OVERCAST_K",
]

# Reference colour temperatures, in kelvin. Named because "2000" means nothing
# at a call site and "CANDLE_K" means exactly what the light is.
CANDLE_K = 1900
TUNGSTEN_K = 2800
DAYLIGHT_K = 5600
OVERCAST_K = 7500


def kelvin_to_rgb(kelvin: float) -> tuple[int, int, int]:
    """Approximate the sRGB colour of a blackbody radiator at `kelvin`.

    Tanner Helland's piecewise fit to the blackbody locus — accurate enough for
    art direction across roughly 1000-40000 K, and cheap. Below ~1900 K the fit
    saturates to pure red-orange, which is also roughly what a real flame does.

    Returns channels clamped to 0-255.
    """
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0

    if t <= 66:
        r = 255.0
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)

    if t <= 66:
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)

    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307

    clamp = lambda v: int(round(max(0.0, min(255.0, v))))  # noqa: E731
    return clamp(r), clamp(g), clamp(b)


def kelvin_to_hex(kelvin: float, alpha: int = 255) -> str:
    """Blackbody colour as Rive's `#aarrggbb`.

    Note the channel order: Rive takes **alpha first**, unlike CSS's `#rrggbbaa`.
    Getting this backwards yields a fully transparent shape, which looks like a
    build failure rather than a colour mistake.
    """
    r, g, b = kelvin_to_rgb(kelvin)
    a = max(0, min(255, int(alpha)))
    return f"#{a:02x}{r:02x}{g:02x}{b:02x}"


def falloff_stops(
    kelvin: float,
    *,
    steps: int = 8,
    exponent: float = 2.0,
    core_alpha: int = 255,
    spread: float = 7.0,
) -> list[dict[str, Any]]:
    """Gradient stops for a radial light, shaped so it reads as light.

    `position` is a percentage of the radius and `alpha` follows
    `1 / (1 + spread * d) ** exponent`, normalised to reach exactly zero at the
    rim.

    **`spread` is what makes this look like a lamp rather than a disc.** The
    obvious formulation — `1 / (1 + d) ** 2` across d in 0..1 — is inverse-square
    arithmetic, but it treats the whole shape as one radius of falloff, so the
    core is still half-opaque at quarter-radius and the result renders as a flat
    coin with a soft rim. Real glow has a small bright core and a long faint
    tail: `spread` sets how many falloff radii fit inside the shape, and 7 puts
    the half-brightness point at about 6% of the radius, which is roughly where
    a flame sits inside its own halo.

    **Step count matters as much as the curve.** Rive interpolates linearly
    between gradient stops, so a five-stop gradient is four straight ramps and
    the first one — from full to half opacity — is visible as an edge. Eight is
    where the piecewise line stops reading as a line.

    Raising `exponent` tightens the core further; lowering it spreads the light.
    """
    if steps < 2:
        raise ValueError("a gradient needs at least two stops")
    if exponent <= 0:
        raise ValueError("exponent must be positive")
    if spread <= 0:
        raise ValueError("spread must be positive")

    floor = 1.0 / ((1.0 + spread) ** exponent)
    stops: list[dict[str, Any]] = []
    for i in range(steps):
        d = i / (steps - 1)  # 0 at the core, 1 at the rim
        raw = 1.0 / ((1.0 + spread * d) ** exponent)
        norm = (raw - floor) / (1.0 - floor)
        alpha = int(round(core_alpha * max(0.0, min(1.0, norm))))
        stops.append({"color": kelvin_to_hex(kelvin, alpha), "position": d * 100.0})
    # The outermost stop must be exactly transparent or the light has a visible
    # edge where the gradient ends.
    stops[-1]["color"] = kelvin_to_hex(kelvin, 0)
    return stops


def flicker(frame: int, *, seed: int = 0, amplitude: float = 0.12,
            base: float = 1.0) -> float:
    """A reproducible flame flicker as a multiplier on intensity.

    A sum of three incommensurate sines. Because their periods share no common
    factor the pattern does not visibly repeat, but it is entirely determined by
    `frame` and `seed` — so re-running the pipeline produces a byte-identical
    file, which random noise would not.

    Returns `base` modulated by at most `amplitude`, never negative.
    """
    phase = seed * 0.7391
    v = (
        math.sin(frame * 0.31 + phase)
        + 0.6 * math.sin(frame * 0.73 + phase * 2.1)
        + 0.3 * math.sin(frame * 1.55 + phase * 3.7)
    ) / 1.9
    return max(0.0, base + amplitude * v)


@dataclass(frozen=True)
class LightRig:
    """A three-point lighting setup, in artboard coordinates.

    Key, fill and rim are the standard film arrangement: the key does the
    modelling, the fill lifts the shadow side without flattening it, and the rim
    separates the subject from the background. Expressed here as positions plus
    intensities so the scene engine can place real lights from one call.
    """

    key: tuple[float, float]
    key_intensity: float
    key_kelvin: float
    fill: tuple[float, float]
    fill_intensity: float
    fill_kelvin: float
    rim: tuple[float, float]
    rim_intensity: float
    rim_kelvin: float


def three_point(
    subject: tuple[float, float],
    *,
    distance: float = 200.0,
    key_side: str = "left",
    ratio: float = 2.0,
    key_kelvin: float = TUNGSTEN_K,
    fill_kelvin: float = OVERCAST_K,
    rim_kelvin: float = DAYLIGHT_K,
) -> LightRig:
    """Place a key, fill and rim around `subject`.

    `ratio` is the classic key-to-fill lighting ratio: 2 is gentle, 4 is
    dramatic, 8 is film noir. The fill is deliberately COOLER than the key,
    because warm key against cool shadow is what reads as depth — the same
    principle the studio's palette is built on.

    The key sits 30 degrees off axis and slightly above, the fill opposite and
    level, the rim behind and high.
    """
    if key_side not in ("left", "right"):
        raise ValueError("key_side must be 'left' or 'right'")
    if ratio < 1:
        raise ValueError("ratio must be at least 1 (key is never dimmer than fill)")

    sx, sy = subject
    sign = -1.0 if key_side == "left" else 1.0
    rad = math.radians(30)

    key = (sx + sign * distance * math.cos(rad), sy - distance * math.sin(rad))
    fill = (sx - sign * distance * 0.9, sy)
    rim = (sx - sign * distance * 0.5, sy - distance * 1.1)

    return LightRig(
        key=key,
        key_intensity=1.0,
        key_kelvin=key_kelvin,
        fill=fill,
        fill_intensity=1.0 / ratio,
        fill_kelvin=fill_kelvin,
        rim=rim,
        rim_intensity=0.75,
        rim_kelvin=rim_kelvin,
    )


# --------------------------------------------------------------------------- #
# Authoring
# --------------------------------------------------------------------------- #

#: Channels the lantern exposes, all driven from `useRiveChannels`.
LANTERN_CHANNELS = {
    "glow": "number",      # halo opacity, 0-100
    "coreGlow": "number",  # flame core opacity, 0-100
    "haloScale": "number", # halo scale percentage
    "flameScale": "number",# flame scale percentage, the flicker
    "swing": "number",     # lantern rotation in degrees
    "beam": "number",      # cast pool opacity, 0-100
}


def build_lantern(mcp: RiveMCP, *, kelvin: float = CANDLE_K,
                  verbose: bool = True) -> dict[str, Any]:
    """Authors a `light/lantern` artboard: a hanging lamp that swings and flickers.

    Built back to front, because child index 0 is FRONTMOST in Rive and the halo
    must sit behind the glass it is escaping from.
    """
    from .uikit import KEY, KitBuilder, ensure_kit_view_model  # local: shared plumbing

    b = KitBuilder(mcp, verbose=verbose)
    ab = b.artboard("light/lantern", 260, 320)
    b.transparent_artboard(ab)

    warm = kelvin_to_hex(kelvin)
    # The halo is the widest light in the piece, so it needs the most stops:
    # Rive interpolates linearly between them, and across a 280px radius a
    # five-stop gradient shows its first straight ramp as a visible edge.
    stops = falloff_stops(kelvin, steps=8)

    def radial(name: str, *, x: float, y: float, w: float, h: float,
               stop_list: list[dict[str, Any]]) -> tuple[str, str]:
        r = mcp.call("path_editor", {"command": "createParametricShapes", "data": {
            "createParametricShapes": {"shapes": [{
                "primitive": "ellipse", "name": name, "parentId": ab,
                "x": x, "y": y, "width": w, "height": h,
                "paints": [{"paintType": "fill",
                            "gradient": {"type": "radial", "stops": stop_list}}],
            }]}}})
        s = r["shapes"][0]
        return s["id"], s["pathId"]

    # 1. The pool of light the lantern casts on the ground — widest, furthest back.
    beam, _ = radial("cast-pool", x=130, y=286, w=250, h=70,
                     stop_list=falloff_stops(kelvin, steps=8, exponent=1.4,
                                             core_alpha=120, spread=4.0))
    # 2. The halo around the lamp itself.
    halo, _ = radial("halo", x=130, y=150, w=280, h=280, stop_list=stops)
    # 3. The lantern body: a glass box with a warm interior.
    b.rect(ab, "glass", x=130, y=150, w=96, h=120, radius=10,
           color="#1affffff", stroke="#66ffffff", stroke_width=2)
    # 4. The flame core, brightest and smallest.
    flame, _ = radial("flame", x=130, y=158, w=58, h=80,
                      stop_list=falloff_stops(kelvin, steps=6, exponent=2.6,
                                              spread=3.0))
    # 5. Hardware: the cap and the hanging cord.
    b.rect(ab, "cap", x=130, y=86, w=104, h=16, radius=4, color="#ff2a3140")
    b.rect(ab, "cord", x=130, y=40, w=3, h=76, color="#ff3b4354")

    vm_id, prop_ids = ensure_kit_view_model(
        mcp, extra=list(LANTERN_CHANNELS), verbose=verbose
    )
    instances = mcp.call("viewmodel_editor", {
        "command": "listViewModelInstances",
        "data": {"listViewModelInstances": {"viewModelId": vm_id}}})["instances"]
    mcp.call("viewmodel_editor", {"command": "bindViewModelToArtboard", "data": {
        "bindViewModelToArtboard": {"artboardId": ab, "viewModelId": vm_id,
                                    "viewModelInstanceId": instances[0]["id"]}}})

    channels = {
        "glow": (halo, KEY["opacity"]),
        "coreGlow": (flame, KEY["opacity"]),
        "haloScale": (halo, KEY["scaleX"]),
        "flameScale": (flame, KEY["scaleY"]),
        "swing": (halo, KEY["rotation"]),
        "beam": (beam, KEY["opacity"]),
    }
    missing = [ch for ch in channels if ch not in prop_ids]
    if missing:
        raise RuntimeError(f"kit view model is missing channels: {missing}")
    bindings = [{"objectId": oid, "propertyKey": pk,
                 "viewModelPropertyId": prop_ids[ch]}
                for ch, (oid, pk) in channels.items()]
    mcp.call("viewmodel_editor", {"command": "databind", "data": {
        "databind": {"viewModelId": vm_id, "bindings": bindings}}})
    b.log(f"lantern: bound {len(bindings)} channels at {kelvin:.0f}K ({warm})")

    return {"artboardId": ab, "channels": list(channels), "kelvin": kelvin}
