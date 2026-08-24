"""Music engine: prompt construction, format gating, and shot-to-music timing.

Generation itself is a network call and is not unit-tested; what is tested is
everything around it — the decisions that determine whether a cue is usable.
"""

import pathlib

import pytest

from genassets.music import (
    CUE_STYLES,
    RIVE_AUDIO_FORMATS,
    Cue,
    MusicEngine,
    MusicError,
    describe_shots,
)


@pytest.fixture
def engine(monkeypatch, tmp_path) -> MusicEngine:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return MusicEngine(out_dir=tmp_path)


def cue(mime: str = "audio/mpeg", size: int = 1024) -> Cue:
    return Cue(path=pathlib.Path(f"x.{mime.split('/')[-1]}"), mime_type=mime,
               bytes_len=size, prompt="")


class TestPrompt:
    def test_includes_the_mood_and_duration(self, engine):
        p = engine.build_prompt("a rocket launch at night", seconds=15)
        assert "15-second" in p
        assert "rocket launch at night" in p

    def test_expands_a_named_style(self, engine):
        p = engine.build_prompt("liftoff", style="cinematic-rise")
        assert CUE_STYLES["cinematic-rise"] in p

    def test_passes_an_unknown_style_through_verbatim(self, engine):
        p = engine.build_prompt("liftoff", style="like a music box")
        assert "like a music box" in p

    def test_always_asks_for_instrumental_by_default(self, engine):
        # Vocals fight with UI and dialogue and cannot loop cleanly.
        assert "no vocals" in engine.build_prompt("anything")

    def test_vocals_can_be_allowed_explicitly(self, engine):
        assert "no vocals" not in engine.build_prompt("a song", instrumental=False)

    def test_always_asks_for_headroom(self, engine):
        # The cue plays under an animation, not in front of it.
        assert "headroom" in engine.build_prompt("anything").lower()

    def test_shot_notes_are_included(self, engine):
        notes = describe_shots([("push-in", 60)])
        assert "push in" in engine.build_prompt("x", shot_notes=notes)


class TestDescribeShots:
    def test_converts_frames_to_seconds(self):
        out = describe_shots([("push-in", 60), ("shake", 30)], fps=60)
        assert "0.0s-1.0s" in out
        assert "1.0s-1.5s" in out

    def test_reports_the_total_duration(self):
        out = describe_shots([("a", 120), ("b", 60)], fps=60)
        assert "total 3.0s" in out

    def test_humanises_shot_names(self):
        assert "push in on rocket" in describe_shots([("push-in-on-rocket", 60)])

    def test_an_empty_shot_list_yields_nothing(self):
        assert describe_shots([]) == ""

    def test_respects_a_different_frame_rate(self):
        assert "0.0s-1.0s" in describe_shots([("a", 24)], fps=24)


class TestCue:
    def test_mp3_is_rive_compatible(self):
        c = cue("audio/mpeg")
        assert c.extension == "mp3"
        assert c.rive_compatible

    def test_wav_and_flac_are_compatible(self):
        assert cue("audio/wav").rive_compatible
        assert cue("audio/flac").rive_compatible

    def test_an_unknown_audio_mime_defaults_to_mp3_but_is_NOT_compatible(self):
        # The mp3 fallback keeps a novel label from producing a nonsense
        # extension - but it must NOT mark the format as Rive-compatible, or the
        # failure moves from here into the editor.
        c = cue("audio/something-new")
        assert c.extension == "mp3"
        assert not c.rive_compatible

    def test_a_non_audio_mime_does_not_masquerade_as_mp3(self):
        assert cue("application/octet-stream").extension == "bin"

    def test_reports_size_in_megabytes(self):
        # Audio dominates the payload of any Rive file carrying it, so size is
        # a first-class property rather than a detail.
        assert cue(size=2 * 1024 * 1024).megabytes == pytest.approx(2.0)

    def test_summarises_sections(self):
        c = Cue(path=pathlib.Path("x.mp3"), mime_type="audio/mpeg", bytes_len=1,
                prompt="", sections=[("A", 0), ("A", 1), ("B", 2)])
        assert c.section_summary() == "3 sections: A A B"

    def test_reports_when_there_are_no_sections(self):
        assert "no section markers" in cue().section_summary()


class TestAttachToRive:
    def test_refuses_a_format_rive_cannot_take(self, engine):
        bad = Cue(path=pathlib.Path("x.ogg"), mime_type="audio/ogg",
                  bytes_len=1, prompt="")
        # Fails here rather than uploading something the editor rejects later.
        with pytest.raises(MusicError, match="Rive accepts"):
            engine.attach_to_rive(bad)

    def test_uploads_a_compatible_cue(self, engine):
        class FakeMCP:
            def __init__(self): self.calls = []
            def call(self, tool, args):
                self.calls.append((tool, args))
                return {"assetId": "9-1", "type": "audio"}

        mcp = FakeMCP()
        result = engine.attach_to_rive(cue("audio/mpeg"), mcp=mcp)
        assert result["type"] == "audio"
        tool, args = mcp.calls[0]
        assert tool == "upload_asset"
        # The parameter is `file`, and for audio the extension is what Rive
        # uses to detect the type - it does not sniff audio content.
        assert "file" in args
        assert args["file"].endswith(".mpeg") or args["file"].endswith(".mp3")


class TestConfig:
    def test_a_missing_key_fails_immediately(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(MusicError, match="GEMINI_API_KEY"):
            MusicEngine()

    def test_rive_audio_formats_match_what_the_editor_accepts(self):
        # From upload_asset's own description: audio (mp3/wav/flac).
        assert RIVE_AUDIO_FORMATS == {"mp3", "wav", "flac"}
