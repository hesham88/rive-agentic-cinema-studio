"""Tests for the facet splitter.

The geometry is the whole value here — a fold placed wrong reads as damage
rather than as a crease — so these assert on measurable properties: area is
conserved, both faces share the seam exactly, and the fold follows the form's
long axis rather than an arbitrary direction.
"""

import math

import pytest

from genassets.facet import (
    centroid,
    commands_from_polygon,
    dominant_axis,
    facet_shapes,
    polygon_from_commands,
    shade,
    split_polygon,
)

# The real traced hero, straight out of the pipeline.
PLANE = [
    (183, -116), (185, -116), (180, -109), (45, 104), (-58, 50),
    (-79, 116), (-100, 29), (-184, -9), (162, -110),
]

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]


def area(pts):
    """Shoelace, unsigned."""
    n = len(pts)
    return abs(sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                   for i in range(n))) / 2


class TestCommands:
    def test_round_trips_a_polygon(self):
        assert polygon_from_commands(commands_from_polygon(SQUARE)) == SQUARE

    def test_reads_cubic_endpoints_and_drops_controls(self):
        cmds = [
            {"commandType": "moveTo", "x": 0, "y": 0},
            {"commandType": "cubicTo", "control1X": 1, "control1Y": 9,
             "control2X": 2, "control2Y": 9, "endX": 3, "endY": 4},
        ]
        assert polygon_from_commands(cmds) == [(0.0, 0.0), (3.0, 4.0)]

    def test_output_is_closed(self):
        assert commands_from_polygon(SQUARE)[-1]["commandType"] == "close"

    def test_refuses_a_degenerate_face(self):
        with pytest.raises(ValueError):
            commands_from_polygon([(0, 0), (1, 1)])


class TestCentroid:
    def test_square(self):
        cx, cy = centroid(SQUARE)
        assert (round(cx, 6), round(cy, 6)) == (5.0, 5.0)

    def test_is_area_weighted_not_the_vertex_mean(self):
        # Three vertices bunched at one end — as a plane's nose is. The vertex
        # mean is pulled toward the cluster; the area centroid is not.
        bunched = [(0, 0), (10, 0), (10, 1), (10, 2), (0, 2)]
        cx, _ = centroid(bunched)
        mean_x = sum(p[0] for p in bunched) / len(bunched)
        assert abs(cx - 5.0) < abs(mean_x - 5.0)

    def test_collinear_points_do_not_divide_by_zero(self):
        cx, cy = centroid([(0, 0), (1, 1), (2, 2)])
        assert math.isfinite(cx) and math.isfinite(cy)


class TestDominantAxis:
    def test_finds_a_horizontal_form(self):
        angle = dominant_axis([(-50, -2), (50, -2), (50, 2), (-50, 2)])
        assert abs(math.sin(angle)) < 0.1

    def test_finds_a_vertical_form(self):
        angle = dominant_axis([(-2, -50), (2, -50), (2, 50), (-2, 50)])
        assert abs(math.cos(angle)) < 0.1

    def test_follows_the_plane_nose_to_tail(self):
        # The hero runs upper-right to lower-left, so its axis is a shallow
        # negative slope. A fold across the wings instead of along the spine
        # would cut the mark in half.
        angle = dominant_axis(PLANE)
        assert -0.9 < math.tan(angle) < -0.1


class TestSplit:
    def test_both_faces_together_conserve_area(self):
        near, far = split_polygon(SQUARE, (5, 5), 0.0)
        assert area(near) + area(far) == pytest.approx(area(SQUARE), rel=1e-9)

    def test_a_centre_cut_halves_a_square(self):
        near, far = split_polygon(SQUARE, (5, 5), 0.0)
        assert area(near) == pytest.approx(50, rel=1e-9)
        assert area(far) == pytest.approx(50, rel=1e-9)

    def test_faces_share_the_seam_exactly(self):
        # A seam mismatch of even a fraction of a pixel shows as a hairline
        # against a dark ground.
        near, far = split_polygon(SQUARE, (5, 5), 0.0)
        shared = {(round(x, 9), round(y, 9)) for x, y in near} & {
            (round(x, 9), round(y, 9)) for x, y in far}
        assert len(shared) >= 2

    def test_a_cut_outside_the_shape_leaves_one_face_empty(self):
        near, far = split_polygon(SQUARE, (100, 100), 0.0)
        assert len(near) == 0 or len(far) == 0

    def test_the_plane_splits_into_two_real_faces(self):
        near, far = split_polygon(PLANE, centroid(PLANE), dominant_axis(PLANE))
        assert len(near) >= 3 and len(far) >= 3
        assert area(near) + area(far) == pytest.approx(area(PLANE), rel=1e-6)


class TestShade:
    def test_darkens_and_lightens(self):
        assert shade("#ff808080", 0.5) == "#ff404040"
        assert shade("#ff808080", 1.5) == "#ffc0c0c0"

    def test_preserves_alpha(self):
        assert shade("#80ff0000", 0.5).startswith("#80")

    def test_clamps_rather_than_wrapping(self):
        # Wrapping would turn a near-white highlight into a dark colour.
        assert shade("#fff0f0f0", 4.0) == "#ffffffff"

    def test_accepts_six_digit_hex_as_opaque(self):
        assert shade("#808080", 1.0) == "#ff808080"

    def test_rejects_a_malformed_colour(self):
        with pytest.raises(ValueError):
            shade("#abc", 1.0)


class TestFacetShapes:
    def _shape(self):
        return {
            "name": "path2",
            "artboardId": "ab",
            "paths": [{"commands": commands_from_polygon(PLANE)}],
            "paints": [{"paintType": "fill", "color": "#ff757b80"}],
        }

    def test_produces_two_faces(self):
        out = facet_shapes(self._shape())
        assert len(out) == 2
        assert [s["name"] for s in out] == ["path2-near", "path2-far"]

    def test_the_faces_differ_in_tone(self):
        # The entire point: a fold has to be visible as a hard edge between two
        # tones, or the form reads flat.
        near, far = facet_shapes(self._shape())
        assert near["paints"][0]["color"] != far["paints"][0]["color"]

    def test_the_near_face_is_lighter(self):
        near, far = facet_shapes(self._shape())
        lum = lambda c: sum(int(c[i:i + 2], 16) for i in (3, 5, 7))
        assert lum(near["paints"][0]["color"]) > lum(far["paints"][0]["color"])

    def test_the_tonal_spread_is_wide_enough_to_read(self):
        near, far = facet_shapes(self._shape())
        lum = lambda c: sum(int(c[i:i + 2], 16) for i in (3, 5, 7)) / 3
        assert lum(near["paints"][0]["color"]) - lum(far["paints"][0]["color"]) > 25

    def test_carries_other_shape_fields_through(self):
        for s in facet_shapes(self._shape()):
            assert s["artboardId"] == "ab"

    def test_offset_moves_the_fold(self):
        centred = facet_shapes(self._shape())
        moved = facet_shapes(self._shape(), offset=0.2)
        a = area(polygon_from_commands(centred[0]["paths"][0]["commands"]))
        b = area(polygon_from_commands(moved[0]["paths"][0]["commands"]))
        assert a != pytest.approx(b, rel=1e-6)

    def test_refuses_a_shape_with_no_paths(self):
        with pytest.raises(ValueError):
            facet_shapes({"name": "x", "paths": []})

    def test_refuses_a_shape_too_simple_to_fold(self):
        with pytest.raises(ValueError):
            facet_shapes({
                "name": "x",
                "paths": [{"commands": commands_from_polygon([(0, 0), (1, 0), (0, 1)])}],
                "paints": [{"color": "#ffffffff"}],
            })
