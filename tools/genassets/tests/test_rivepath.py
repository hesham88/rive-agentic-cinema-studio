import math

import pytest

from genassets.rivepath import (
    PathBudgetExceeded,
    parse_path,
    svg_color_to_rive,
)


def kinds(cmds):
    return [c["commandType"] for c in cmds]


class TestBasicCommands:
    def test_moveto_lineto_close(self):
        cmds = parse_path("M 10 20 L 30 40 Z")
        assert kinds(cmds) == ["moveTo", "lineTo", "close"]
        assert (cmds[0]["x"], cmds[0]["y"]) == (10, 20)
        assert (cmds[1]["x"], cmds[1]["y"]) == (30, 40)

    def test_relative_commands_accumulate(self):
        cmds = parse_path("m 10 10 l 5 5 l 5 5")
        assert [(c["x"], c["y"]) for c in cmds] == [(10, 10), (15, 15), (20, 20)]

    def test_horizontal_and_vertical(self):
        cmds = parse_path("M 0 0 H 50 V 25 h -10 v -5")
        assert [(c["x"], c["y"]) for c in cmds[1:]] == [(50, 0), (50, 25), (40, 25), (40, 20)]

    def test_implicit_repeat_after_moveto_is_lineto(self):
        # Per the SVG spec, extra coordinate pairs after M are implicit L.
        cmds = parse_path("M 0 0 10 10 20 20")
        assert kinds(cmds) == ["moveTo", "lineTo", "lineTo"]

    def test_cubic(self):
        cmds = parse_path("M 0 0 C 1 2 3 4 5 6")
        c = cmds[1]
        assert c["commandType"] == "cubicTo"
        assert (c["control1X"], c["control1Y"]) == (1, 2)
        assert (c["control2X"], c["control2Y"]) == (3, 4)
        assert (c["endX"], c["endY"]) == (5, 6)


class TestConversions:
    def test_quadratic_becomes_cubic_exactly(self):
        # Degree elevation: controls sit 2/3 of the way toward the quad control.
        cmds = parse_path("M 0 0 Q 30 0 30 30")
        c = cmds[1]
        assert c["commandType"] == "cubicTo"
        assert c["control1X"] == pytest.approx(20.0)
        assert c["control1Y"] == pytest.approx(0.0)
        assert c["control2X"] == pytest.approx(30.0)
        assert c["control2Y"] == pytest.approx(10.0)

    def test_smooth_cubic_reflects_previous_control(self):
        cmds = parse_path("M 0 0 C 10 0 20 0 30 0 S 50 0 60 0")
        c = cmds[2]
        # Reflection of (20,0) about the current point (30,0) is (40,0).
        assert c["control1X"] == pytest.approx(40.0)

    def test_smooth_quad_reflects_previous_control(self):
        cmds = parse_path("M 0 0 Q 10 10 20 0 T 40 0")
        assert kinds(cmds) == ["moveTo", "cubicTo", "cubicTo"]

    def test_arc_becomes_cubics_and_lands_on_endpoint(self):
        cmds = parse_path("M 0 0 A 50 50 0 0 1 100 0")
        assert all(c["commandType"] == "cubicTo" for c in cmds[1:])
        last = cmds[-1]
        assert last["endX"] == pytest.approx(100.0, abs=1e-6)
        assert last["endY"] == pytest.approx(0.0, abs=1e-6)

    def test_degenerate_arc_becomes_a_line(self):
        cmds = parse_path("M 0 0 A 0 0 0 0 1 10 10")
        assert kinds(cmds) == ["moveTo", "lineTo"]

    def test_full_circle_via_two_arcs_returns_to_start(self):
        cmds = parse_path("M 0 0 A 25 25 0 1 1 50 0 A 25 25 0 1 1 0 0")
        last = cmds[-1]
        assert last["endX"] == pytest.approx(0.0, abs=1e-6)
        assert last["endY"] == pytest.approx(0.0, abs=1e-6)


class TestRobustness:
    def test_scientific_notation_and_no_separators(self):
        cmds = parse_path("M1e1 2.5L-3.5.5")
        assert (cmds[0]["x"], cmds[0]["y"]) == (10.0, 2.5)
        assert (cmds[1]["x"], cmds[1]["y"]) == (-3.5, 0.5)

    def test_multiple_subpaths(self):
        cmds = parse_path("M 0 0 L 10 0 Z M 20 20 L 30 20 Z")
        assert kinds(cmds).count("moveTo") == 2
        assert kinds(cmds).count("close") == 2

    def test_close_returns_pen_to_subpath_start(self):
        cmds = parse_path("M 5 5 L 10 10 Z l 1 1")
        # After Z the pen is back at (5,5), so a relative l lands at (6,6).
        assert (cmds[-1]["x"], cmds[-1]["y"]) == (6, 6)

    def test_path_starting_with_a_number_is_rejected(self):
        with pytest.raises(ValueError, match="starts with a number"):
            parse_path("10 20 L 30 40")

    def test_truncated_command_is_rejected(self):
        with pytest.raises(ValueError, match="truncated"):
            parse_path("M 10 20 C 1 2 3")

    def test_budget_is_enforced(self):
        with pytest.raises(PathBudgetExceeded):
            parse_path("M 0 0 " + "L 1 1 " * 50, max_commands=10)


class TestColor:
    def test_six_digit_hex_gains_opaque_alpha_first(self):
        # Rive wants #aarrggbb — alpha FIRST. Passing web #rrggbb misreads channels.
        assert svg_color_to_rive("#ff8800") == "#ffff8800"

    def test_three_digit_hex_expands(self):
        assert svg_color_to_rive("#f80") == "#ffff8800"

    def test_opacity_becomes_alpha(self):
        assert svg_color_to_rive("#000000", opacity=0.5) == "#80000000"

    def test_eight_digit_hex_passes_through(self):
        assert svg_color_to_rive("#80ff0000") == "#80ff0000"

    def test_rgb_function(self):
        assert svg_color_to_rive("rgb(255, 136, 0)") == "#ffff8800"

    def test_rgba_function_alpha(self):
        assert svg_color_to_rive("rgba(0, 0, 0, 0.5)") == "#80000000"

    def test_unsupported_color_raises(self):
        with pytest.raises(ValueError):
            svg_color_to_rive("chartreuse")
