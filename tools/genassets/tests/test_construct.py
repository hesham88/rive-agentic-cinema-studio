"""The construction engine: primitives, geometric shading, and the recipes.

The tests that matter here are the ones that can catch a WRONG PICTURE, not
just a crash. Three do real work:

`test_light_direction_puts_the_shadow_away_from_the_key` catches an inverted
light, which renders as uplighting and is invisible to any structural check.

`test_local_colour_is_what_reaches_the_colour_band` pins the finding that took
two rebuilds to arrive at: shading every form from six shared palette roles
grades out at 8 colours against a 24-36 target, however many forms are added.

`test_every_recipe_meets_the_house_standard` is the end-to-end gate. It is the
one that failed first — the engine's own output was rejected by the project's
own grader at 37 paths and 8 colours — which is what makes it worth having.
"""

from __future__ import annotations

import math

import pytest

from genassets.construct import (
    KEY_UPPER_LEFT, PALETTES, Form, Light, contact_shadow, crescent, ellipse,
    polygon, shade_form, tapered, tint, transform, wedge,
)
from genassets.facet import polygon_from_commands
from genassets.recipes import RECIPES, build
from genassets.standard import grade


def pts(cmds):
    return polygon_from_commands(cmds)


def centre(points):
    n = len(points)
    return sum(p[0] for p in points) / n, sum(p[1] for p in points) / n


# --- primitives -----------------------------------------------------------

def test_ellipse_is_closed_and_round() -> None:
    cmds = ellipse(0, 0, 50, 50, segments=16)
    assert cmds[0]["commandType"] == "moveTo"
    assert cmds[-1]["commandType"] == "close"
    for p in pts(cmds):
        assert math.hypot(*p) == pytest.approx(50, rel=1e-6)


def test_ellipse_segments_control_vertex_count() -> None:
    """Vertex placement is a rigging decision made at draw time: a form that
    will bend needs vertices where the bend falls."""
    assert len(pts(ellipse(0, 0, 10, 10, segments=4))) == 5
    assert len(pts(ellipse(0, 0, 10, 10, segments=20))) == 21


def test_ellipse_rejects_a_degenerate_segment_count() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        ellipse(0, 0, 10, 10, segments=2)


def test_tapered_actually_tapers() -> None:
    """A limb with equal ends is a sausage — rejection-checklist item 7."""
    cmds = tapered(0, 0, 100, 0, 40, 10, round_end=False)
    p = pts(cmds)
    start_w = abs(p[0][1] - p[3][1])
    end_w = abs(p[1][1] - p[2][1])
    assert start_w == pytest.approx(40)
    assert end_w == pytest.approx(10)
    assert end_w < start_w


def test_tapered_rejects_zero_length() -> None:
    with pytest.raises(ValueError, match="two distinct endpoints"):
        tapered(5, 5, 5, 5, 10, 4)


def test_transform_rotates_about_the_given_pivot() -> None:
    square = polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    turned = transform(square, rotate=90, about=(5, 5))
    cx, cy = centre(pts(turned))
    assert (cx, cy) == pytest.approx((5, 5), abs=1e-6)


def test_transform_scale_and_translate_compose() -> None:
    square = polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    moved = transform(square, scale=2, dx=100)
    xs = [p[0] for p in pts(moved)]
    assert min(xs) == pytest.approx(100)
    assert max(xs) == pytest.approx(120)


# --- light ----------------------------------------------------------------

def test_light_direction_puts_the_shadow_away_from_the_key() -> None:
    """An inverted light renders as uplighting and no structural test sees it.

    The house key is upper-front-left, travelling down-right, so the shadow
    crescent must sit down-right of centre and the highlight up-left.
    """
    form = pts(ellipse(0, 0, 100, 100, segments=24))
    shadow = centre(crescent(form, KEY_UPPER_LEFT, inset=0.30, coverage=0.46))
    highlight = centre(crescent(form, KEY_UPPER_LEFT, inset=0.66,
                                coverage=0.26, toward_light=True))
    assert shadow[0] > 0 and shadow[1] > 0, "shadow must fall away from the key"
    assert highlight[0] < 0 and highlight[1] < 0, "highlight must face the key"


def test_reversing_the_light_reverses_the_shading() -> None:
    form = pts(ellipse(0, 0, 100, 100, segments=24))
    a = centre(crescent(form, Light(1, 1), inset=0.3, coverage=0.4))
    b = centre(crescent(form, Light(-1, -1), inset=0.3, coverage=0.4))
    assert a[0] * b[0] < 0 and a[1] * b[1] < 0


def test_crescent_stays_inside_the_form() -> None:
    """A shadow poking outside its own silhouette is the classic offset bug."""
    r = 100.0
    form = pts(ellipse(0, 0, r, r, segments=32))
    for region in (crescent(form, KEY_UPPER_LEFT, inset=0.30, coverage=0.46),
                   crescent(form, KEY_UPPER_LEFT, inset=0.62, coverage=0.30)):
        for x, y in region:
            assert math.hypot(x, y) <= r + 1e-6


def test_crescent_of_a_degenerate_form_is_empty() -> None:
    assert crescent([(0, 0), (1, 1)], KEY_UPPER_LEFT) == []


# --- colour ---------------------------------------------------------------

def test_tint_produces_a_distinct_but_related_colour() -> None:
    base = "#8BE3E0"
    shifted = tint(base, hue=-20, sat=0.2, val=-0.3)
    assert shifted != base
    assert shifted.startswith("#") and len(shifted) == 7


def test_tint_clamps_rather_than_wrapping_value() -> None:
    """Wrapping would turn a highlight into a black hole."""
    assert tint("#ffffff", val=0.9) == "#ffffff"
    assert tint("#000000", val=-0.9) == "#000000"


def test_shade_form_emits_the_full_tonal_ladder() -> None:
    out = shade_form(Form("f", ellipse(0, 0, 50, 40, segments=16)),
                     KEY_UPPER_LEFT, PALETTES["underwater-shallow"])
    names = [s["name"].rsplit("-", 1)[-1] for s in out]
    assert names == ["base", "halftone", "shadow", "bounce", "highlight", "rim"]
    assert len({s["paints"][0]["color"] for s in out}) == len(out), "tones must differ"


def test_the_darkest_band_is_not_on_the_silhouette_edge() -> None:
    """The single most common lighting error in generated art, per the craft
    research — and the one the first version of `shade_form` committed.

    A real form shows the terminator at ~0.72 along the light axis and the
    darkest value at 0.72-0.90, with 0.90-1.00 lifting again from bounced
    light. Painting the darkest value hard against the outline instead reads as
    a dark stroke drawn around the shape.

    So the bounce band must be painted AFTER the core shadow — later means on
    top — and must be lighter than it.
    """
    out = shade_form(Form("f", ellipse(0, 0, 60, 60, segments=24)),
                     KEY_UPPER_LEFT, PALETTES["underwater-shallow"])
    by_name = {s["name"].rsplit("-", 1)[-1]: i for i, s in enumerate(out)}
    assert by_name["bounce"] > by_name["shadow"], "bounce must overlay the core shadow"

    def luminance(shape):
        c = shape["paints"][0]["color"][3:]
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    assert luminance(out[by_name["bounce"]]) > luminance(out[by_name["shadow"]])


def test_the_base_keeps_the_true_curve() -> None:
    """Regions are polygons; the base must stay bezier or the silhouette
    degrades to a polygon and the whole point is lost."""
    cmds = ellipse(0, 0, 50, 40, segments=16)
    out = shade_form(Form("f", cmds), KEY_UPPER_LEFT, PALETTES["wonder"])
    base = out[0]["paths"][0]["commands"]
    assert any(c["commandType"] == "cubicTo" for c in base)


def test_rim_can_be_suppressed_for_an_inset_form() -> None:
    """A scute set into a shell has no lit outer edge of its own."""
    out = shade_form(Form("scute", ellipse(0, 0, 20, 14, segments=10), rim=False),
                     KEY_UPPER_LEFT, PALETTES["underwater-shallow"])
    assert not any(s["name"].endswith("-rim") for s in out)


def test_unshaded_form_is_a_single_flat_shape() -> None:
    out = shade_form(Form("eye", ellipse(0, 0, 5, 5), shade=False),
                     KEY_UPPER_LEFT, PALETTES["dread"])
    assert len(out) == 1


def test_local_colour_is_what_reaches_the_colour_band() -> None:
    """The finding that took two rebuilds.

    Six palette roles shared across every form cannot produce 24-36 colours
    however many forms are added, because the forms all resolve to the same few
    base tones. Distinct local materials are the mechanism.
    """
    pal = PALETTES["underwater-shallow"]
    shared = []
    for i in range(6):
        shared += shade_form(Form(f"s{i}", ellipse(i * 30, 0, 20, 20, segments=10)),
                             KEY_UPPER_LEFT, pal)
    local = []
    for i in range(6):
        local += shade_form(
            Form(f"l{i}", ellipse(i * 30, 0, 20, 20, segments=10),
                 local=tint(pal.key, hue=-8 * i, sat=0.04 * i, val=-0.05 * i)),
            KEY_UPPER_LEFT, pal)

    shared_colours = {s["paints"][0]["color"] for s in shared}
    local_colours = {s["paints"][0]["color"] for s in local}
    assert len(shared_colours) <= 6, "shared roles collapse onto a handful of tones"
    assert len(local_colours) >= 20, "local materials are what open the colour range"


def test_contact_shadow_is_wide_flat_and_translucent() -> None:
    s = contact_shadow(0, 100, 200, palette=PALETTES["warm-optimism"])
    p = pts(s["paths"][0]["commands"])
    w = max(x for x, _ in p) - min(x for x, _ in p)
    h = max(y for _, y in p) - min(y for _, y in p)
    assert w == pytest.approx(200)
    assert h < w * 0.5, "a contact shadow is squashed, not a circle"
    assert int(s["paints"][0]["color"][1:3], 16) < 255, "must be translucent"


def test_contact_shadow_rejects_impossible_opacity() -> None:
    with pytest.raises(ValueError, match="0..1"):
        contact_shadow(0, 0, 10, palette=PALETTES["dread"], opacity=1.4)


# --- recipes, end to end --------------------------------------------------

@pytest.mark.parametrize("name", sorted(RECIPES))
def test_every_recipe_meets_the_house_standard(name: str) -> None:
    """The gate that rejected this engine's own first output."""
    built = build(RECIPES[name]())
    verdict = grade(built.path_count, len(built.colours))
    assert verdict.passed, f"{name}: {verdict}"


@pytest.mark.parametrize("name", sorted(RECIPES))
def test_every_recipe_carries_a_bone_plan_and_motion_notes(name: str) -> None:
    built = build(RECIPES[name]())
    assert built.bones, f"{name} has no bone plan"
    assert built.bones[0][1] is None, "the first bone must be a root"
    parents = {b for b, _ in built.bones}
    for bone, parent in built.bones:
        assert parent is None or parent in parents, f"{bone} has an unknown parent"
    assert built.motion_notes, f"{name} has no motion notes"


def test_the_turtle_records_that_it_flies_rather_than_rows() -> None:
    """The fundamental sea-turtle error, per the craft notes. Recording it in
    the recipe is what stops the animation stage getting it wrong."""
    notes = " ".join(build(RECIPES["sea-turtle"]()).motion_notes).lower()
    assert "flap" in notes and "not row" in notes
    assert "rudder" in notes
    assert "rigid" in notes


def test_recipes_do_not_invent_a_number_the_literature_lacks() -> None:
    """Sea-turtle stroke frequency is NR. Filling an NR is explicitly forbidden."""
    notes = " ".join(build(RECIPES["sea-turtle"]()).motion_notes)
    assert "NR" in notes


def test_recipes_scale_by_their_base_unit() -> None:
    from genassets.recipes import sea_turtle
    small = build(sea_turtle(u=50))
    large = build(sea_turtle(u=200))
    assert small.path_count == large.path_count

    def extent(b):
        xs = [c["x"] for s in b.shapes for c in s["paths"][0]["commands"] if "x" in c]
        return max(xs) - min(xs)

    assert extent(large) == pytest.approx(extent(small) * 4, rel=1e-6)


# --- perceptual quantisation ----------------------------------------------

def test_delta_e_ranks_colours_the_way_an_eye_does() -> None:
    from genassets.construct import delta_e
    assert delta_e("#8BE3E0", "#8BE3E1") < 1.0, "one bit apart is imperceptible"
    assert delta_e("#8BE3E0", "#064B67") > 40.0, "key vs shadow is obviously two colours"


def test_merge_collapses_invisible_neighbours_and_keeps_real_ones() -> None:
    from genassets.construct import merge_near_duplicates
    shapes = [
        {"name": "a", "paints": [{"color": "#ff8BE3E0"}], "paths": []},
        {"name": "b", "paints": [{"color": "#ff8BE3E1"}], "paths": []},
        {"name": "c", "paints": [{"color": "#ff064B67"}], "paths": []},
    ]
    out = merge_near_duplicates(shapes, threshold=3.0)
    assert len({s["paints"][0]["color"] for s in out}) == 2
    assert out[0]["paints"][0]["color"] == out[1]["paints"][0]["color"]
    assert out[2]["paints"][0]["color"] == "#ff064B67"


def test_merge_never_crosses_an_alpha_boundary() -> None:
    """A translucent contact shadow and an opaque body colour are not the same
    paint, however close their RGB."""
    from genassets.construct import merge_near_duplicates
    shapes = [
        {"name": "a", "paints": [{"color": "#ff064B67"}], "paths": []},
        {"name": "b", "paints": [{"color": "#59064B67"}], "paths": []},
    ]
    out = merge_near_duplicates(shapes, threshold=50.0)
    assert len({s["paints"][0]["color"] for s in out}) == 2


def test_merge_is_what_brings_the_recipes_into_the_colour_band() -> None:
    """Without quantisation every recipe overshoots on near-duplicates — the
    same failure that left the one traced asset at 84 colours."""
    for name in RECIPES:
        raw = build(RECIPES[name](), merge=0)
        merged = build(RECIPES[name]())
        assert len(merged.colours) <= len(raw.colours)
        assert grade(merged.path_count, len(merged.colours)).passed


def test_merge_disabled_keeps_every_tone() -> None:
    from genassets.construct import merge_near_duplicates
    shapes = [{"name": str(i), "paints": [{"color": f"#ff8BE3E{i}"}], "paths": []}
              for i in range(4)]
    assert len({s["paints"][0]["color"]
                for s in merge_near_duplicates(shapes, threshold=0)}) == 4
