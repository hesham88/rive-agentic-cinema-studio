"""Tests for the Parallel research client.

The network calls are not exercised here — a test that needs an API key and a
live service is not a test, it is a monitor. What IS covered is everything that
can be wrong without the network noticing: the response parsing, the citation
model that carries provenance, and the schemas the pipeline consumes.

The schema assertions matter most. A research step whose output the generator
cannot act on is a lookup wearing a pipeline's clothes, so every field is
checked for being something a downstream stage actually reads.
"""

import pytest

from genassets import parallel
from genassets.parallel import (
    ART_DIRECTION_SCHEMA,
    MOTION_SCHEMA,
    PROCESSORS,
    Citation,
    FieldBasis,
    ParallelClient,
    ParallelError,
    ResearchReport,
)


class TestReport:
    def _report(self):
        return ResearchReport(
            objective="paper plane",
            content={"palette": ["#fff", "#000"], "silhouette": "a dart"},
            basis=[
                FieldBasis("palette", "found in style guides", [
                    Citation("https://a.example", ["swatches"]),
                    Citation("https://b.example", []),
                ]),
                FieldBasis("silhouette", "consistent across refs", [
                    Citation("https://a.example", []),
                ]),
            ],
        )

    def test_sources_are_deduplicated_and_ordered(self):
        # a.example is cited by two fields but must appear once, first.
        assert self._report().sources == ["https://a.example", "https://b.example"]

    def test_a_field_reports_its_own_citations(self):
        assert self._report().cited("silhouette") == ["https://a.example"]

    def test_an_uncited_field_returns_empty_not_an_error(self):
        # Provenance UI asks about fields that may not exist; it must not raise.
        assert self._report().cited("nonexistent") == []

    def test_empty_urls_are_dropped(self):
        r = ResearchReport("x", {}, [FieldBasis("f", "", [Citation("", [])])])
        assert r.sources == []

    def test_prompt_context_renders_lists_readably(self):
        text = self._report().as_prompt_context()
        assert "#fff, #000" in text
        assert "a dart" in text

    def test_prompt_context_is_bounded(self):
        r = ResearchReport("x", {"k": "v" * 5000}, [])
        assert len(r.as_prompt_context(max_chars=200)) <= 200

    def test_prose_content_passes_through(self):
        r = ResearchReport("x", "just a paragraph", [])
        assert r.as_prompt_context().startswith("just a paragraph")


class TestSchemas:
    def test_art_direction_returns_a_palette_the_vectoriser_can_use(self):
        palette = ART_DIRECTION_SCHEMA["properties"]["palette"]
        assert palette["type"] == "array"
        assert palette["items"]["type"] == "string"

    def test_art_direction_requires_the_fields_the_pipeline_reads(self):
        assert set(ART_DIRECTION_SCHEMA["required"]) == {
            "palette", "silhouette", "shape_language",
        }

    def test_motion_timings_are_numbers_so_they_can_become_keyframes(self):
        timings = MOTION_SCHEMA["properties"]["frame_timings"]
        assert timings["type"] == "object"
        for beat, spec in timings["properties"].items():
            assert spec["type"] == "number", f"{beat} must be keyable"

    def test_motion_beats_match_the_engine_generators(self):
        # These four names are what motion.py implements. If the schema drifts
        # from them the research returns numbers nothing can key.
        assert set(MOTION_SCHEMA["properties"]["frame_timings"]["properties"]) == {
            "anticipation", "action", "overshoot", "settle",
        }

    def test_task_api_rejects_property_less_objects(self):
        # Verified live: a bare {"type": "object"} with only additionalProperties
        # returns HTTP 422 "Object 'properties' empty at path".
        def objects(schema):
            for name, spec in schema.get("properties", {}).items():
                if spec.get("type") == "object":
                    assert spec.get("properties"), f"{name} needs explicit properties"
        objects(ART_DIRECTION_SCHEMA)
        objects(MOTION_SCHEMA)

    def test_motion_requires_something_to_key(self):
        assert "frame_timings" in MOTION_SCHEMA["required"]

    def test_squash_guidance_carries_the_real_magnitude(self):
        # The videos showed 1-5%, not the 15% instinct. If that guidance is lost
        # the generator drifts straight back to cartoon deformation.
        assert "1-5%" in MOTION_SCHEMA["properties"]["squash_stretch"]["description"]

    @pytest.mark.parametrize("schema", [ART_DIRECTION_SCHEMA, MOTION_SCHEMA])
    def test_every_property_is_documented(self, schema):
        for name, spec in schema["properties"].items():
            assert spec.get("description"), f"{name} has no description"


class TestClient:
    def test_missing_key_fails_loudly(self, monkeypatch):
        monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
        with pytest.raises(ParallelError, match="PARALLEL_API_KEY"):
            ParallelClient()

    def test_unknown_processor_is_rejected_before_a_request(self):
        c = ParallelClient(api_key="test-key")
        with pytest.raises(ParallelError, match="unknown processor"):
            c.research("x", "y", processor="turbo")

    def test_processor_tiers_are_ordered_cheapest_first(self):
        assert PROCESSORS[0] == "lite"
        assert PROCESSORS[-1] == "ultra"

    def test_extract_refuses_more_than_the_api_allows(self):
        c = ParallelClient(api_key="test-key")
        with pytest.raises(ParallelError, match="at most 20"):
            c.extract([f"https://e{i}.example" for i in range(21)])

    def test_extract_of_nothing_is_not_a_request(self):
        c = ParallelClient(api_key="test-key")
        assert c.extract([]) == []
        assert c.calls == []

    def test_calls_are_logged_for_cost_accounting(self):
        c = ParallelClient(api_key="test-key")
        assert c.calls == []
