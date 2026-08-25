"""The artboard clips, so fitted art must survive its own animation.

These tests replay the worst frame an envelope promises — peak rotation, peak
scale and peak drift applied at once — and assert every vertex is still inside
the artboard. That is the property the shipped pipeline violated: art was fitted
to 88% of the frame and then animated, so wingtips left the canvas.

A test that only asserted "margin > 0.06" would pass on any larger number and
prove nothing. Replaying the transform can fail, which is the point.
"""

from __future__ import annotations

import math

import pytest

from genassets.svgdoc import ENVELOPES, MotionEnvelope, SvgShape, to_create_shapes_payload

W = H = 500.0


def square(size: float = 100.0) -> list[SvgShape]:
    return [SvgShape(
        name="s",
        commands=[
            {"commandType": "moveTo", "x": 0, "y": 0},
            {"commandType": "lineTo", "x": size, "y": 0},
            {"commandType": "lineTo", "x": size, "y": size},
            {"commandType": "lineTo", "x": 0, "y": size},
            {"commandType": "close"},
        ],
        fill="#ffffffff",
        min_x=0, min_y=0, max_x=size, max_y=size,
    )]


def worst_frame(payload: list[dict], env: MotionEnvelope) -> list[tuple[float, float]]:
    """Every vertex at peak rotation, peak scale and peak drift, in artboard space."""
    shape = payload[0]
    ox, oy = shape["x"], shape["y"]
    t = math.radians(env.rotation)
    cos_t, sin_t = math.cos(t), math.sin(t)
    out = []
    for c in shape["paths"][0]["commands"]:
        if "x" not in c:
            continue
        x, y = c["x"] * env.scale, c["y"] * env.scale
        rx = x * cos_t - y * sin_t
        ry = x * sin_t + y * cos_t
        out.append((ox + rx + env.drift_x * W, oy + ry + env.drift_y * H))
    return out


@pytest.mark.parametrize("name", sorted(ENVELOPES))
def test_art_survives_its_own_animation(name: str) -> None:
    env = ENVELOPES[name]
    payload = to_create_shapes_payload(square(), artboard_width=W, artboard_height=H, envelope=name)
    for x, y in worst_frame(payload, env):
        assert 0 <= x <= W, f"{name}: vertex x={x:.1f} left the {W:.0f}px artboard"
        assert 0 <= y <= H, f"{name}: vertex y={y:.1f} left the {H:.0f}px artboard"


def test_the_old_flat_margin_actually_clipped() -> None:
    """The regression this fixes. 6% is not enough for a banking hero."""
    env = ENVELOPES["hero-glide"]
    payload = to_create_shapes_payload(square(), artboard_width=W, artboard_height=H, margin=0.06)
    escaped = [p for p in worst_frame(payload, env) if not (0 <= p[0] <= W and 0 <= p[1] <= H)]
    assert escaped, "expected the old 6% margin to clip a hero-glide; if not, this test is wrong"


def test_wide_art_is_not_stretched() -> None:
    """Fitting preserves aspect ratio — a 4:1 mark stays 4:1."""
    wide = [SvgShape(
        name="w",
        commands=[
            {"commandType": "moveTo", "x": 0, "y": 0},
            {"commandType": "lineTo", "x": 400, "y": 0},
            {"commandType": "lineTo", "x": 400, "y": 100},
            {"commandType": "close"},
        ],
        fill="#ffffffff", min_x=0, min_y=0, max_x=400, max_y=100,
    )]
    cmds = to_create_shapes_payload(wide, artboard_width=W, artboard_height=H,
                                    envelope="static")[0]["paths"][0]["commands"]
    xs = [c["x"] for c in cmds if "x" in c]
    ys = [c["y"] for c in cmds if "y" in c]
    assert (max(xs) - min(xs)) / (max(ys) - min(ys)) == pytest.approx(4.0, rel=1e-3)


def test_drift_beyond_the_frame_shrinks_rather_than_crops() -> None:
    """A nonsense envelope must not silently produce cropped art."""
    assert MotionEnvelope(drift_x=0.9).margin() == 0.45


def test_rotation_factor_peaks_at_45_degrees() -> None:
    assert MotionEnvelope(rotation=0).rotation_factor() == pytest.approx(1.0)
    assert MotionEnvelope(rotation=45).rotation_factor() == pytest.approx(math.sqrt(2))
    assert MotionEnvelope(rotation=90).rotation_factor() == pytest.approx(1.0)


def test_unknown_envelope_names_itself() -> None:
    with pytest.raises(ValueError, match="unknown envelope"):
        to_create_shapes_payload(square(), artboard_width=W, artboard_height=H, envelope="nope")
