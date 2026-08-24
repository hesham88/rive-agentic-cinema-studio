"""Tests for the UI kit's pure logic.

The MCP-driven parts need a live editor, so they are not covered here. What is
covered is everything that can be wrong without the editor noticing: the channel
union, the widget declarations, and the palette's colour format — each of which
has already caused a real bug.
"""

from genassets import uikit


def test_channel_union_is_deduplicated():
    union = uikit._channel_union()
    assert len(union) == len(set(union))


def test_channel_union_covers_every_widget():
    union = set(uikit._channel_union())
    for widget in uikit.WIDGETS:
        assert set(widget.properties) <= union, widget.name


def test_shared_channel_names_are_intentional():
    # A slider and a progress bar both call their bar `fillW`. That is safe
    # because each artboard is instanced separately at runtime — but if it ever
    # stops being deliberate, this test is where it will be noticed.
    users = [w.name for w in uikit.WIDGETS if "fillW" in w.properties]
    assert users == ["ui/slider", "ui/progress"]


def test_every_widget_declares_a_view_model_name():
    for w in uikit.WIDGETS:
        assert w.view_model.endswith("VM"), w.name


def test_rest_values_only_name_declared_channels():
    # A resting value for a channel the widget does not declare is silently
    # dropped at build time, so the widget would paint wrong on its first frame.
    for w in uikit.WIDGETS:
        assert set(w.rest) <= set(w.properties), w.name


def test_widget_names_are_unique():
    names = [w.name for w in uikit.WIDGETS]
    assert len(names) == len(set(names))


def test_palette_is_argb_hex():
    # Rive takes #aarrggbb, NOT the #rrggbbaa the web uses. Getting this
    # backwards produces fully transparent shapes that look like a broken build.
    for name, value in uikit.PALETTE.items():
        assert value.startswith("#"), name
        assert len(value) == 9, f"{name} must be #aarrggbb, got {value}"
        int(value[1:], 16)


def test_clear_is_fully_transparent():
    assert uikit.PALETTE["clear"][1:3] == "00"


def test_property_keys_are_positive_integers():
    for name, key in uikit.KEY.items():
        assert isinstance(key, int) and key > 0, name


def test_kit_artboard_names_match_widgets():
    assert uikit.KIT_ARTBOARD_NAMES == [w.name for w in uikit.WIDGETS]
