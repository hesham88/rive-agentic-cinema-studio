"""The gate that would have caught every asset the owner rejected.

The bands come from cited research, not taste — see
`_OPERATIONS/study/craft/09-prompting-for-vectorisable-art.md`. These tests pin
the numbers so a later edit that quietly relaxes them fails here.
"""

from __future__ import annotations

import pytest

from genassets.standard import (
    ANTI_CLAUSES, COLOUR_BAND, PATH_BAND, PATH_MAX, REQUIRED_CLAUSES,
    TONAL_STEPS, grade, house_prompt,
)


def test_the_shipped_hero_would_have_failed() -> None:
    """2 paths / 2 colours — the asset the owner called primitive."""
    g = grade(2, 2)
    assert not g.passed
    assert any("80-160" in r for r in g.reasons)
    assert any("24-36" in r for r in g.reasons)


def test_an_in_band_hero_passes_cleanly() -> None:
    g = grade(120, 30)
    assert g.passed and g.reasons == ()


def test_too_many_colours_warns_without_failing() -> None:
    """The extreme paper plane: 91 paths but 84 colours — usable, needs quantising."""
    g = grade(91, 84)
    assert g.passed
    assert any("perceptual distance" in r for r in g.reasons)


def test_path_ceiling_is_fatal() -> None:
    assert not grade(PATH_MAX + 1, 30).passed


def test_strict_false_downgrades_to_a_warning() -> None:
    """A UI glyph genuinely needs few paths — but the exception stays visible."""
    g = grade(6, 4, strict=False)
    assert g.passed
    assert g.reasons, "a deliberate exception must still report why it is one"


def test_house_prompt_carries_every_required_clause() -> None:
    p = house_prompt("A green sea turtle gliding underwater")
    for clause in REQUIRED_CLAUSES:
        assert clause in p
    assert "A green sea turtle gliding underwater." in p


def test_house_prompt_bans_the_right_things() -> None:
    p = house_prompt("anything")
    assert "smooth gradients" in p and "photorealistic" in p


def test_house_prompt_never_bans_shading_outright() -> None:
    """The regression that flattened every earlier asset.

    "no shading" removes the discrete tonal steps along with the gradients.
    The standard bans continuous rendering and DEMANDS the steps.
    """
    assert "no shading" not in house_prompt("anything").lower()
    assert not any("shading" == c.strip().lower() for c in ANTI_CLAUSES)
    assert f"exactly {TONAL_STEPS} discrete tonal levels" in house_prompt("x")


def test_bands_match_the_cited_research() -> None:
    assert COLOUR_BAND == (24, 36)
    assert PATH_BAND == (80, 160)
    assert TONAL_STEPS == 4
