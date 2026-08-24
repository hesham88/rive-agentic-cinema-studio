"""Tests for the light engine's pure core.

The authoring half needs a live Rive editor, so it is not covered here. What is
covered is the arithmetic that decides whether a light looks like light:
blackbody colour, falloff shape, flicker reproducibility, and rig geometry.
"""

import math

import pytest

from genassets import light


class TestKelvin:
    def test_candle_is_warm(self):
        r, g, b = light.kelvin_to_rgb(light.CANDLE_K)
        assert r > g > b, "a flame must be red-dominant and blue-poor"

    def test_daylight_is_near_neutral(self):
        r, g, b = light.kelvin_to_rgb(light.DAYLIGHT_K)
        assert max(r, g, b) - min(r, g, b) < 60, "5600K should be close to white"

    def test_overcast_is_cooler_than_tungsten(self):
        _, _, cool_b = light.kelvin_to_rgb(light.OVERCAST_K)
        _, _, warm_b = light.kelvin_to_rgb(light.TUNGSTEN_K)
        assert cool_b > warm_b, "higher kelvin must carry more blue"

    def test_channels_stay_in_range(self):
        for k in range(1000, 20001, 250):
            for c in light.kelvin_to_rgb(k):
                assert 0 <= c <= 255

    def test_extremes_are_clamped_not_crashed(self):
        assert light.kelvin_to_rgb(0) == light.kelvin_to_rgb(1000)
        assert light.kelvin_to_rgb(10**9) == light.kelvin_to_rgb(40000)

    def test_hex_is_argb_not_rgba(self):
        # Rive takes alpha FIRST. Reversing it yields transparent shapes, which
        # look like a broken build rather than a colour bug.
        h = light.kelvin_to_hex(light.CANDLE_K, alpha=255)
        assert h.startswith("#ff"), h
        assert len(h) == 9

    def test_hex_alpha_is_honoured(self):
        assert light.kelvin_to_hex(light.CANDLE_K, alpha=0).startswith("#00")


class TestFalloff:
    def test_starts_opaque_and_ends_transparent(self):
        stops = light.falloff_stops(light.CANDLE_K)
        assert stops[0]["color"].startswith("#ff")
        assert stops[-1]["color"].startswith("#00")

    def test_positions_span_the_full_radius(self):
        stops = light.falloff_stops(light.CANDLE_K, steps=5)
        assert stops[0]["position"] == 0
        assert stops[-1]["position"] == 100

    def test_alpha_decreases_monotonically(self):
        stops = light.falloff_stops(light.CANDLE_K, steps=6)
        alphas = [int(s["color"][1:3], 16) for s in stops]
        assert alphas == sorted(alphas, reverse=True)

    def test_falloff_is_not_linear(self):
        # The whole point. A linear ramp gives a flat disc with a hard edge;
        # inverse-square gives a hot core. The midpoint must sit BELOW half.
        stops = light.falloff_stops(light.CANDLE_K, steps=3, exponent=2.0)
        mid_alpha = int(stops[1]["color"][1:3], 16)
        assert mid_alpha < 255 * 0.5

    def test_higher_exponent_tightens_the_light(self):
        soft = light.falloff_stops(light.CANDLE_K, steps=3, exponent=1.2)
        hard = light.falloff_stops(light.CANDLE_K, steps=3, exponent=3.0)
        assert int(hard[1]["color"][1:3], 16) < int(soft[1]["color"][1:3], 16)

    def test_step_count_is_respected(self):
        assert len(light.falloff_stops(light.CANDLE_K, steps=7)) == 7

    def test_rejects_degenerate_input(self):
        with pytest.raises(ValueError):
            light.falloff_stops(light.CANDLE_K, steps=1)
        with pytest.raises(ValueError):
            light.falloff_stops(light.CANDLE_K, exponent=0)


class TestFlicker:
    def test_is_reproducible(self):
        # Reproducibility is why this is sines and not random: the same prompt
        # must produce the same file twice.
        a = [light.flicker(f, seed=3) for f in range(200)]
        b = [light.flicker(f, seed=3) for f in range(200)]
        assert a == b

    def test_seeds_differ(self):
        a = [light.flicker(f, seed=1) for f in range(100)]
        b = [light.flicker(f, seed=2) for f in range(100)]
        assert a != b

    def test_stays_within_amplitude(self):
        for f in range(1000):
            v = light.flicker(f, amplitude=0.2, base=1.0)
            assert 0.8 - 1e-9 <= v <= 1.2 + 1e-9

    def test_never_goes_negative(self):
        # A negative intensity would invert the gradient rather than dim it.
        for f in range(500):
            assert light.flicker(f, amplitude=5.0, base=0.1) >= 0.0

    def test_actually_varies(self):
        vals = {round(light.flicker(f), 4) for f in range(120)}
        assert len(vals) > 100, "a flicker that barely moves is not a flicker"

    def test_does_not_visibly_repeat(self):
        # Incommensurate periods: the pattern must not cycle within a few seconds.
        a = [round(light.flicker(f), 6) for f in range(60)]
        b = [round(light.flicker(f + 60), 6) for f in range(60)]
        assert a != b


class TestThreePoint:
    def test_fill_is_dimmer_than_key_by_the_ratio(self):
        rig = light.three_point((0, 0), ratio=4)
        assert rig.key_intensity / rig.fill_intensity == pytest.approx(4)

    def test_fill_is_cooler_than_key(self):
        # Warm key against cool shadow is what reads as depth.
        rig = light.three_point((0, 0))
        assert rig.fill_kelvin > rig.key_kelvin

    def test_key_and_fill_sit_on_opposite_sides(self):
        rig = light.three_point((0, 0), key_side="left")
        assert rig.key[0] < 0 < rig.fill[0]
        flipped = light.three_point((0, 0), key_side="right")
        assert flipped.fill[0] < 0 < flipped.key[0]

    def test_key_is_above_the_subject(self):
        rig = light.three_point((0, 0))
        assert rig.key[1] < 0, "screen y grows downward; the key is raised"

    def test_rim_is_highest(self):
        rig = light.three_point((0, 0))
        assert rig.rim[1] < rig.key[1]

    def test_distance_scales_the_rig(self):
        near = light.three_point((0, 0), distance=100)
        far = light.three_point((0, 0), distance=400)
        assert math.hypot(*far.key) > math.hypot(*near.key)

    def test_rejects_impossible_setups(self):
        with pytest.raises(ValueError):
            light.three_point((0, 0), key_side="above")
        with pytest.raises(ValueError):
            light.three_point((0, 0), ratio=0.5)
