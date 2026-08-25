"""Licence gating and SVG sanitisation for externally-sourced art.

Two things are being defended here and both are worth failing a build over.

A wrong licence call is a legal problem that no test elsewhere would catch —
CC BY-SA is copyleft and would oblige this MIT project to relicense, yet its
string contains "cc by", so a naive allowlist admits it. `test_share_alike_*`
pins that.

A hostile SVG is a security problem, because these files come from the open
internet and end up inside a web page. The sanitiser tests use actual attack
shapes rather than a token `<script>` tag.

Nothing here touches the network. Live fetching is exercised by hand; unit
tests that depend on Wikimedia's current contents would fail for reasons that
have nothing to do with this code.
"""

from __future__ import annotations

import pytest

from genassets.sourcing import (
    LicenceRejected, SourcedArt, licence_ok, sanitise_svg, fetch_art,
)


# --- licensing ------------------------------------------------------------

@pytest.mark.parametrize("licence", [
    "CC0", "CC0 1.0", "Public domain", "PDM-owner", "PD-old-70",
    "No restrictions", "CC BY 4.0", "CC BY 3.0", "CC BY 2.5",
])
def test_permissive_licences_are_allowed(licence: str) -> None:
    assert licence_ok(licence)


@pytest.mark.parametrize("licence", [
    "CC BY-SA 3.0", "CC BY-SA 4.0", "Attribution-ShareAlike 4.0",
    "CC BY-NC 2.0", "CC BY-NC-SA 4.0", "CC BY-ND 4.0",
    "GFDL", "Fair use", "GPL",
])
def test_incompatible_licences_are_rejected(licence: str) -> None:
    assert not licence_ok(licence)


def test_share_alike_is_rejected_despite_containing_cc_by() -> None:
    """The trap. Rejection must run BEFORE the allowlist, or copyleft slips in."""
    assert "cc by" in "CC BY-SA 4.0".lower()
    assert not licence_ok("CC BY-SA 4.0")


def test_missing_licence_is_rejected_not_assumed() -> None:
    """A source that stops reporting metadata must not start yielding
    unlicensed files."""
    assert not licence_ok("")
    assert not licence_ok("   ")


def test_fetch_raises_rather_than_returning_a_rejected_licence() -> None:
    with pytest.raises(LicenceRejected, match="not usable"):
        fetch_art({"title": "x", "licence": "CC BY-SA 4.0", "file_url": "http://e/x.svg"})


# --- sanitisation ---------------------------------------------------------

def test_script_element_is_removed() -> None:
    out, removed = sanitise_svg('<svg><script>fetch("//evil")</script><path d="M0 0"/></svg>')
    assert "script" not in out.lower() and "evil" not in out
    assert any("script" in r for r in removed)
    assert '<path d="M0 0"/>' in out, "sanitising must preserve the actual geometry"


def test_event_handlers_are_removed() -> None:
    out, removed = sanitise_svg('<svg><circle onload="steal()" onclick=\'x()\' r="5"/></svg>')
    assert "onload" not in out and "onclick" not in out
    assert 'r="5"' in out
    assert any("event handler" in r for r in removed)


def test_external_references_are_removed_but_internal_kept() -> None:
    svg = ('<svg><use href="https://evil.test/x.svg#a"/>'
           '<use href="#local"/><image xlink:href="http://evil.test/p.png"/></svg>')
    out, removed = sanitise_svg(svg)
    assert "evil.test" not in out
    assert 'href="#local"' in out, "internal fragment refs are legitimate"
    assert removed


def test_javascript_urls_are_removed() -> None:
    out, _ = sanitise_svg("""<svg><a href="javascript:alert(1)"><path d="M0 0"/></a></svg>""")
    assert "javascript:" not in out


def test_entity_declarations_are_removed() -> None:
    """Billion-laughs and external-entity vectors live in the DTD."""
    svg = '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg><path d="M0 0"/></svg>'
    out, removed = sanitise_svg(svg)
    assert "ENTITY" not in out and "DOCTYPE" not in out
    assert any("doctype" in r for r in removed)


def test_foreign_object_is_removed() -> None:
    out, _ = sanitise_svg('<svg><foreignObject><iframe src="//evil"/></foreignObject></svg>')
    assert "foreignObject" not in out and "iframe" not in out


def test_clean_svg_is_left_alone() -> None:
    svg = '<svg viewBox="0 0 10 10"><path d="M0 0 L10 10" fill="#ff0000"/></svg>'
    out, removed = sanitise_svg(svg)
    assert out == svg
    assert removed == [], "a clean file must report no removals"


# --- attribution ----------------------------------------------------------

def test_saving_always_writes_attribution(tmp_path) -> None:
    art = SourcedArt(
        title="Sea Turtle", svg='<svg><path d="M0 0"/></svg>', licence="CC BY 4.0",
        artist="Somebody", source_url="https://commons.example/File:Sea_Turtle.svg",
        file_url="https://upload.example/Sea_Turtle.svg",
    )
    path = art.save(tmp_path)
    assert path.exists()
    record = (tmp_path / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert "Sea Turtle" in record and "CC BY 4.0" in record and "Somebody" in record
    assert path.name in record


def test_attribution_is_not_duplicated_on_resave(tmp_path) -> None:
    art = SourcedArt(title="X", svg="<svg/>", licence="CC0", artist="A",
                     source_url="https://s/1", file_url="https://f/1.svg")
    art.save(tmp_path)
    art.save(tmp_path)
    record = (tmp_path / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert record.count("https://s/1") == 1


# --- trademarks ------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Fox Broadcasting Company logo 2019", "Dolphin-logo", "Jellyfish Media logo",
    "Matra Sports logo", "Fox wordmark orange", "Some Network emblem",
])
def test_brand_assets_are_recognised(title: str) -> None:
    """A permissive licence on a file depicting a trademark grants no trademark
    rights. Seven of the first twenty-five files fetched were corporate logos."""
    from genassets.sourcing import looks_like_a_brand
    assert looks_like_a_brand(title)


@pytest.mark.parametrize("title", [
    "Sea Turtle", "A Butterfly 2", "Green turtle", "Seahorse lifecycle",
    "Sloop psf", "Bottlenose dolphin",
])
def test_real_illustrations_are_not_flagged(title: str) -> None:
    from genassets.sourcing import looks_like_a_brand
    assert not looks_like_a_brand(title)


# --- background plates -----------------------------------------------------

def test_plate_with_style_fill_across_lines_is_caught() -> None:
    """The jellyfish case: fill inside `style`, tag spanning many lines."""
    from genassets.sourcing import has_background_plate
    svg = '''<svg viewBox="0 0 210 297"><rect
       y="-0.29" x="-0.44"
       height="299.0" width="211.0"
       id="rect3844"
       style="fill:#000000;fill-opacity:1;stroke:none" /></svg>'''
    assert has_background_plate(svg)


def test_plate_with_no_fill_attribute_is_caught() -> None:
    """SVG defaults a missing fill to BLACK, not transparent."""
    from genassets.sourcing import has_background_plate
    assert has_background_plate('<svg viewBox="0 0 100 100"><rect width="100" height="100"/></svg>')


def test_transparent_full_bleed_rect_is_fine() -> None:
    from genassets.sourcing import has_background_plate
    assert not has_background_plate(
        '<svg viewBox="0 0 100 100"><rect width="100" height="100" fill="none"/></svg>')


def test_small_rect_is_not_a_plate() -> None:
    from genassets.sourcing import has_background_plate
    assert not has_background_plate(
        '<svg viewBox="0 0 100 100"><rect width="20" height="12" fill="#f00"/></svg>')


def test_fetch_refuses_a_file_with_its_own_background() -> None:
    from genassets.sourcing import has_background_plate
    assert has_background_plate('<svg viewBox="0 0 50 50"><rect width="50" height="50" fill="#000"/></svg>')
