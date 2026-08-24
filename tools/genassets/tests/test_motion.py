"""Motion craft principles.

Each test pins the property that makes the principle *work* — not just that
keyframes were produced. A stagger with no offset is not a stagger; an
anticipation that eases the same way in both directions is a wobble.
"""

import pytest

from genassets.camera import PROP, ease
from genassets.motion import (
    anticipate,
    arc,
    breathe,
    follow_through,
    overshoot,
    parallax_factor,
    parallax_shift,
    stagger,
)

IDS = ["a", "b", "c", "d"]


def frames_for(kfs, oid):
    return [k["frame"] for k in kfs if k["objectId"] == oid]


class TestStagger:
    def test_each_object_starts_later_than_the_last(self):
        kfs = stagger(IDS, PROP["opacity"], start_value=0, end_value=100, step=4)
        starts = [min(frames_for(kfs, o)) for o in IDS]
        assert starts == [0, 4, 8, 12]

    def test_every_object_travels_the_same_distance(self):
        # Only the timing is offset; the motion itself is identical.
        kfs = stagger(IDS, PROP["opacity"], start_value=0, end_value=100, step=3)
        for o in IDS:
            vals = [k["value"] for k in kfs if k["objectId"] == o]
            assert vals == [0, 100]

    def test_duration_is_per_object_not_shared(self):
        kfs = stagger(IDS, PROP["y"], start_value=0, end_value=10,
                      duration=20, step=5)
        for o in IDS:
            f = frames_for(kfs, o)
            assert f[1] - f[0] == 20

    def test_reverse_cascades_from_the_far_end(self):
        # A list should collapse in the opposite order to the one it opened in.
        kfs = stagger(IDS, PROP["opacity"], start_value=100, end_value=0,
                      step=4, reverse=True)
        assert min(frames_for(kfs, "d")) == 0
        assert min(frames_for(kfs, "a")) == 12

    def test_a_single_object_still_works(self):
        assert len(stagger(["solo"], PROP["opacity"], start_value=0, end_value=100)) == 2

    def test_an_empty_list_produces_nothing(self):
        assert stagger([], PROP["opacity"], start_value=0, end_value=1) == []


class TestAnticipate:
    def test_winds_up_against_the_travel(self):
        # Moving right (0 -> 100) must first move LEFT.
        kfs = anticipate("a", PROP["x"], rest=0, target=100)
        assert kfs[1]["value"] < kfs[0]["value"]

    def test_wind_up_scales_with_the_travel(self):
        kfs = anticipate("a", PROP["x"], rest=0, target=100, amount=0.2)
        assert kfs[1]["value"] == pytest.approx(-20)

    def test_it_works_in_the_other_direction_too(self):
        # Moving left must first move RIGHT.
        kfs = anticipate("a", PROP["x"], rest=0, target=-100, amount=0.2)
        assert kfs[1]["value"] == pytest.approx(20)

    def test_the_two_phases_use_opposite_curves(self):
        # Wind-up decelerates into the turnaround; the action accelerates away.
        # One curve for both is what makes it read as a wobble.
        kfs = anticipate("a", PROP["x"], rest=0, target=100)
        assert kfs[1]["cubicParams"] == ease("easeOut")
        assert kfs[2]["cubicParams"] == ease("easeIn")

    def test_it_lands_exactly_on_target(self):
        assert anticipate("a", PROP["x"], rest=0, target=250)[-1]["value"] == 250

    def test_timing_is_windup_then_action(self):
        kfs = anticipate("a", PROP["x"], rest=0, target=1, wind_up=6, action=18)
        assert [k["frame"] for k in kfs] == [0, 6, 24]


class TestOvershoot:
    def test_passes_the_target_before_settling(self):
        kfs = overshoot("a", PROP["x"], start=0, target=100, amount=0.15)
        assert kfs[1]["value"] > 100

    def test_settles_exactly_on_target(self):
        assert overshoot("a", PROP["x"], start=0, target=100)[-1]["value"] == 100

    def test_overshoot_is_proportional_to_travel(self):
        small = overshoot("a", PROP["x"], start=0, target=10, amount=0.1)[1]["value"]
        big = overshoot("a", PROP["x"], start=0, target=1000, amount=0.1)[1]["value"]
        assert small == pytest.approx(11)
        assert big == pytest.approx(1100)

    def test_it_overshoots_downward_when_travelling_down(self):
        kfs = overshoot("a", PROP["y"], start=100, target=0, amount=0.2)
        assert kfs[1]["value"] < 0


class TestFollowThrough:
    def test_the_follower_arrives_late(self):
        lead = overshoot("rocket", PROP["y"], start=0, target=-100)
        trail = follow_through(lead, "flame", delay=6)
        assert [k["frame"] for k in trail] == [f + 6 for f in
                                               [k["frame"] for k in lead]]

    def test_the_follower_travels_less_far(self):
        lead = overshoot("rocket", PROP["y"], start=0, target=-100)
        trail = follow_through(lead, "flame", damping=0.5)
        assert abs(trail[-1]["value"]) < abs(lead[-1]["value"])

    def test_it_retargets_to_the_follower(self):
        lead = stagger(["rocket"], PROP["y"], start_value=0, end_value=50)
        assert {k["objectId"] for k in follow_through(lead, "flame")} == {"flame"}

    def test_it_starts_from_the_same_place_as_the_leader(self):
        # Damping scales the EXCURSION, not the origin - otherwise the follower
        # would begin somewhere the leader never was.
        lead = overshoot("r", PROP["y"], start=40, target=-60)
        trail = follow_through(lead, "f", damping=0.5)
        assert trail[0]["value"] == 40

    def test_an_empty_leader_produces_nothing(self):
        assert follow_through([], "flame") == []


class TestParallax:
    def test_the_focal_plane_moves_with_the_camera(self):
        assert parallax_factor(0.0) == 1.0

    def test_infinite_distance_is_static(self):
        assert parallax_factor(1.0) == 0.0

    def test_nearer_than_focus_moves_more(self):
        # This is what sells a foreground element sweeping past.
        assert parallax_factor(-0.5) == 1.5

    def test_far_layers_shift_less_than_near_ones(self):
        kfs = parallax_shift(
            [("near", 0.1), ("far", 0.8)], PROP["x"],
            camera_delta=200, start_frame=0, end_frame=60)
        near = [k["value"] for k in kfs if k["objectId"] == "near"][-1]
        far = [k["value"] for k in kfs if k["objectId"] == "far"][-1]
        assert abs(near) > abs(far)

    def test_layers_move_opposite_to_the_camera(self):
        kfs = parallax_shift([("l", 0.5)], PROP["x"], camera_delta=100,
                             start_frame=0, end_frame=30)
        assert kfs[-1]["value"] < 0

    def test_every_layer_gets_a_start_and_an_end(self):
        kfs = parallax_shift([("a", 0.2), ("b", 0.4), ("c", 0.6)], PROP["x"],
                             camera_delta=50, start_frame=10, end_frame=70)
        assert len(kfs) == 6
        assert {k["frame"] for k in kfs} == {10, 70}


class TestBreathe:
    def test_returns_to_where_it_started(self):
        kfs = breathe("a", PROP["scaleY"], center=100, amplitude=4, cycles=2)
        assert kfs[0]["value"] == 100
        assert kfs[-1]["value"] == 100

    def test_peaks_at_the_amplitude(self):
        kfs = breathe("a", PROP["scaleY"], center=100, amplitude=6, cycles=1)
        assert max(k["value"] for k in kfs) == pytest.approx(106)

    def test_phase_offsets_the_whole_cycle(self):
        # Siblings breathing in unison read as a strobe, not as life.
        a = breathe("a", PROP["y"], center=0, amplitude=5, period=60, phase=0.0)
        b = breathe("b", PROP["y"], center=0, amplitude=5, period=60, phase=0.5)
        assert a[0]["frame"] != b[0]["frame"]

    def test_more_cycles_produce_more_keyframes(self):
        one = breathe("a", PROP["y"], center=0, amplitude=1, cycles=1)
        three = breathe("a", PROP["y"], center=0, amplitude=1, cycles=3)
        assert len(three) > len(one)


class TestOutputShape:
    def test_frames_are_never_negative(self):
        # A wind-up before frame 0 would silently reorder the timeline.
        kfs = anticipate("a", PROP["x"], rest=0, target=10, start_frame=0)
        assert all(k["frame"] >= 0 for k in kfs)

    def test_every_keyframe_has_what_rive_requires(self):
        for kf in stagger(IDS, PROP["opacity"], start_value=0, end_value=100):
            assert {"objectId", "propertyKey", "frame", "value",
                    "interpolationType"} <= set(kf)


class TestArc:
    def test_it_starts_and_ends_exactly_on_the_endpoints(self):
        kfs = arc("a", start=(0, 0), end=(100, 0), samples=6)
        first_x = [k for k in kfs if k["propertyKey"] == PROP["x"]][0]
        last_x = [k for k in kfs if k["propertyKey"] == PROP["x"]][-1]
        assert first_x["value"] == 0
        assert last_x["value"] == 100

    def test_the_midpoint_leaves_the_straight_line(self):
        # THE POINT OF THE FUNCTION. A straight path would keep y at 0
        # throughout; the arc must depart from the chord.
        kfs = arc("a", start=(0, 0), end=(100, 0), bow=0.3, samples=6)
        ys = [k["value"] for k in kfs if k["propertyKey"] == PROP["y"]]
        assert max(abs(y) for y in ys) > 5

    def test_bow_sign_flips_the_curve(self):
        up = arc("a", start=(0, 0), end=(100, 0), bow=0.3, samples=4)
        down = arc("a", start=(0, 0), end=(100, 0), bow=-0.3, samples=4)
        uy = [k["value"] for k in up if k["propertyKey"] == PROP["y"]]
        dy = [k["value"] for k in down if k["propertyKey"] == PROP["y"]]
        assert max(uy) > 0 and min(dy) < 0

    def test_zero_bow_is_a_straight_line(self):
        kfs = arc("a", start=(0, 0), end=(100, 0), bow=0.0, samples=6)
        ys = [k["value"] for k in kfs if k["propertyKey"] == PROP["y"]]
        assert all(abs(y) < 1e-9 for y in ys)

    def test_samples_control_the_number_of_keys(self):
        # Each key is a handle in the editor, so more is not better.
        few = arc("a", start=(0, 0), end=(10, 10), samples=3)
        many = arc("a", start=(0, 0), end=(10, 10), samples=10)
        assert len(few) == 8 and len(many) == 22

    def test_only_the_endpoints_are_eased(self):
        # Easing the interior keys too would ease an already-shaped curve and
        # stutter the travel.
        kfs = arc("a", start=(0, 0), end=(50, 50), samples=4, easing="easeInOut")
        xs = [k for k in kfs if k["propertyKey"] == PROP["x"]]
        assert xs[0]["cubicParams"] == ease("easeInOut")
        assert xs[-1]["cubicParams"] == ease("easeInOut")
        assert xs[2]["cubicParams"] == ease("linear")

    def test_frames_span_the_requested_duration(self):
        kfs = arc("a", start=(0, 0), end=(1, 1), start_frame=10, duration=60, samples=6)
        frames = sorted({k["frame"] for k in kfs})
        assert frames[0] == 10 and frames[-1] == 70

    def test_a_diagonal_arc_bows_perpendicular_to_its_chord(self):
        # The curve must be perpendicular to the travel, not to an axis.
        kfs = arc("a", start=(0, 0), end=(100, 100), bow=0.3, samples=4)
        mid = len(kfs) // 2
        mx = kfs[mid]["value"] if kfs[mid]["propertyKey"] == PROP["x"] else kfs[mid + 1]["value"]
        # On a pure diagonal the midpoint of a straight line would be (50, 50).
        assert abs(mx - 50) > 5
