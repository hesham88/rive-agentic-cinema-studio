"""Camera maths.

The inversion is what these guard: a camera is simulated by transforming the
world in the OPPOSITE direction. Getting the sign or the order of operations
wrong produces a camera that drifts away from its subject as it zooms — a bug
that looks like a rendering glitch rather than arithmetic.
"""

import pytest

from genassets.camera import (
    PROP,
    CameraRig,
    CameraState,
    dolly,
    ease,
    orbit,
    pan,
    sequence_to_keyframes,
    shake,
    zoom,
)


@pytest.fixture
def rig() -> CameraRig:
    return CameraRig(rig_id="rig-1", viewport_w=1000, viewport_h=600)


class TestRigTransform:
    def test_looking_at_the_origin_centres_the_viewport(self, rig):
        t = rig.rig_transform(CameraState(0, 0, 1.0))
        assert (t["x"], t["y"]) == (500, 300)

    def test_the_rig_moves_opposite_to_the_camera(self, rig):
        # Camera pans right to x=100, so the world must move LEFT by 100.
        t = rig.rig_transform(CameraState(100, 0, 1.0))
        assert t["x"] == 400
        assert t["y"] == 300

    def test_zoom_is_emitted_as_a_percentage_not_a_multiplier(self, rig):
        # Rive takes scale in the units the inspector shows: 100 == 1x.
        # Emitting 2.5 would be read as 2.5%, shrinking the scene to nothing.
        t = rig.rig_transform(CameraState(0, 0, 2.5))
        assert t["scaleX"] == 250.0
        assert t["scaleY"] == 250.0

    def test_identity_zoom_is_one_hundred(self, rig):
        t = rig.rig_transform(CameraState(0, 0, 1.0))
        assert t["scaleX"] == 100.0

    def test_zoom_keeps_the_look_at_point_centred(self, rig):
        # THE ORDER-OF-OPERATIONS TEST. Scaling about the origin and then
        # translating would leave the subject drifting off-centre as it zooms.
        for level in (1.0, 2.0, 4.0):
            t = rig.rig_transform(CameraState(200, 150, level))
            # Where does scene point (200,150) land on screen?
            screen_x = t["x"] + 200 * level
            screen_y = t["y"] + 150 * level
            assert screen_x == pytest.approx(500)
            assert screen_y == pytest.approx(300)

    def test_roll_is_inverted_like_translation(self, rig):
        assert rig.rig_transform(CameraState(roll=15)) ["rotation"] == -15

    def test_zero_zoom_does_not_divide_by_zero(self, rig):
        t = rig.rig_transform(CameraState(10, 10, 0.0))
        assert t["scaleX"] > 0


class TestSequencing:
    def test_a_starting_keyframe_is_always_emitted(self, rig):
        kf = sequence_to_keyframes(rig)
        assert all(k["frame"] == 0 for k in kf)
        assert {k["propertyKey"] for k in kf} == set(PROP[p] for p in
                                                     ("x", "y", "rotation", "scaleX", "scaleY"))

    def test_shots_accumulate_frame_positions(self, rig):
        rig.shots = [pan("a", 100, 0, frames=30), pan("b", 200, 0, frames=45)]
        kf = sequence_to_keyframes(rig)
        assert sorted({k["frame"] for k in kf}) == [0, 30, 75]

    def test_every_keyframe_targets_the_rig(self, rig):
        rig.shots = [dolly("in", 50, 50, 2.0, frames=60)]
        assert {k["objectId"] for k in sequence_to_keyframes(rig)} == {"rig-1"}

    def test_a_dolly_changes_position_and_scale_together(self, rig):
        rig.shots = [dolly("push", 100, 100, 3.0, frames=60)]
        end = [k for k in sequence_to_keyframes(rig) if k["frame"] == 60]
        by_key = {k["propertyKey"]: k["value"] for k in end}
        assert by_key[PROP["scaleX"]] == 300.0
        # Subject still centred at the new zoom.
        assert by_key[PROP["x"]] + 100 * 3.0 == pytest.approx(500)


class TestShake:
    def test_shake_emits_a_keyframe_per_intermediate_frame(self, rig):
        rig.shots = [shake("impact", 8.0, frames=10)]
        kf = sequence_to_keyframes(rig)
        x_frames = sorted(k["frame"] for k in kf if k["propertyKey"] == PROP["x"])
        # frame 0, nine intermediates, and the shot end.
        assert x_frames == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    def test_shake_is_deterministic(self, rig):
        rig.shots = [shake("impact", 8.0, frames=10)]
        assert sequence_to_keyframes(rig) == sequence_to_keyframes(rig)

    def test_shake_stays_within_its_intensity(self, rig):
        rig.shots = [shake("impact", 5.0, frames=20)]
        kf = sequence_to_keyframes(rig)
        base = rig.rig_transform(CameraState())
        for k in kf:
            if k["propertyKey"] == PROP["x"] and 0 < k["frame"] < 20:
                assert abs(k["value"] - base["x"]) <= 5.0 + 1e-6

    def test_no_shake_means_no_intermediate_frames(self, rig):
        rig.shots = [pan("still", 10, 10, frames=20)]
        kf = sequence_to_keyframes(rig)
        assert sorted({k["frame"] for k in kf}) == [0, 20]


class TestEasing:
    def test_named_curves_resolve(self):
        assert ease("linear") == {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
        assert ease("backOut")["y1"] > 1  # overshoots by design

    def test_an_unknown_name_falls_back_to_cinematic(self):
        assert ease("nonsense") == ease("cinematic")

    def test_camera_moves_default_to_cinematic(self, rig):
        rig.shots = [pan("a", 10, 0, frames=10)]
        end = [k for k in sequence_to_keyframes(rig) if k["frame"] == 10][0]
        assert end["cubicParams"] == ease("cinematic")


class TestShotBuilders:
    def test_orbit_sets_roll(self, rig):
        rig.shots = [orbit("canted", 12, frames=30)]
        end = [k for k in sequence_to_keyframes(rig)
               if k["frame"] == 30 and k["propertyKey"] == PROP["rotation"]][0]
        assert end["value"] == -12  # inverted, like every other camera axis

    def test_zoom_holds_the_named_point(self, rig):
        rig.shots = [zoom("closer", 2.0, at_x=300, at_y=200, frames=40)]
        end = {k["propertyKey"]: k["value"] for k in sequence_to_keyframes(rig)
               if k["frame"] == 40}
        assert end[PROP["x"]] + 300 * 2.0 == pytest.approx(500)
        assert end[PROP["y"]] + 200 * 2.0 == pytest.approx(300)
