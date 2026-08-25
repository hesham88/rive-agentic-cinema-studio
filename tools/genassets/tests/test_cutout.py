"""Tests for background removal.

`cutout.py` implements the pipeline's fifth documented finding — key a colour
rather than asking a JPEG for transparency it cannot carry — and had no tests.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from genassets.cutout import (
    DEFAULT_KEY,
    dominant_edge_color,
    key_to_alpha,
    trim_to_content,
)

SUBJECT = (20, 120, 200)


def keyed_image(
    size: tuple[int, int] = (64, 64),
    box: tuple[int, int, int, int] = (16, 16, 48, 48),
    key: tuple[int, int, int] = DEFAULT_KEY,
) -> Image.Image:
    """A solid subject rectangle sitting on a flat key-coloured background."""
    im = Image.new("RGB", size, key)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            im.putpixel((x, y), SUBJECT)
    return im


def write(im: Image.Image, path, fmt: str = "PNG"):
    im.save(path, fmt)
    return path


# ------------------------------------------------------------------ keying

def test_the_key_colour_becomes_transparent(tmp_path):
    src = write(keyed_image(), tmp_path / "a.png")
    out = key_to_alpha(src, tmp_path / "b.png")

    arr = np.asarray(Image.open(out.path).convert("RGBA"))
    assert arr[0, 0, 3] == 0, "a background pixel survived as opaque"


def test_the_subject_stays_opaque(tmp_path):
    src = write(keyed_image(), tmp_path / "a.png")
    out = key_to_alpha(src, tmp_path / "b.png")

    arr = np.asarray(Image.open(out.path).convert("RGBA"))
    assert arr[32, 32, 3] == 255, "the subject was eaten by the tolerance"


def test_reports_the_fraction_actually_removed(tmp_path):
    # A 64x64 image with a 32x32 subject: 1024 of 4096 pixels kept, so 75%
    # should be removed. A reported fraction that does not match what was done
    # is worse than none — it would be trusted.
    src = write(keyed_image(size=(64, 64), box=(16, 16, 48, 48)), tmp_path / "a.png")
    out = key_to_alpha(src, tmp_path / "b.png")
    assert out.removed_fraction == pytest.approx(0.75, abs=0.02)


def test_a_picture_with_no_key_colour_loses_nothing(tmp_path):
    src = write(Image.new("RGB", (32, 32), SUBJECT), tmp_path / "a.png")
    out = key_to_alpha(src, tmp_path / "b.png")
    assert out.removed_fraction == pytest.approx(0.0, abs=0.001)


def test_tolerance_catches_jpeg_smearing_of_the_key(tmp_path):
    """The reason tolerance defaults high: JPEG smears the key at the edge."""
    src = tmp_path / "a.jpg"
    keyed_image(size=(128, 128), box=(32, 32, 96, 96)).save(src, "JPEG", quality=25)

    generous = key_to_alpha(src, tmp_path / "generous.png", tolerance=90)
    strict = key_to_alpha(src, tmp_path / "strict.png", tolerance=2)

    assert generous.removed_fraction > strict.removed_fraction, (
        "a generous tolerance must remove more of a smeared key than a strict one"
    )
    assert generous.removed_fraction > 0.5


def test_despill_removes_the_key_cast_from_surviving_pixels(tmp_path):
    """Without despill a magenta key leaves a visible pink fringe."""
    # A subject pixel deliberately tinted toward the key but outside tolerance.
    im = Image.new("RGB", (16, 16), DEFAULT_KEY)
    for x in range(4, 12):
        for y in range(4, 12):
            im.putpixel((x, y), (200, 60, 200))
    src = write(im, tmp_path / "a.png")

    on = key_to_alpha(src, tmp_path / "on.png", despill=True)
    off = key_to_alpha(src, tmp_path / "off.png", despill=False)

    def greenness(p):
        a = np.asarray(Image.open(p.path).convert("RGBA")).astype(int)
        subject = a[8, 8]
        # Despill pulls the magenta channels down toward green, reducing the
        # red/blue excess that reads as a pink fringe.
        return int(subject[0]) + int(subject[2]) - 2 * int(subject[1])

    assert greenness(on) < greenness(off)


def test_the_key_is_reported_back(tmp_path):
    src = write(keyed_image(key=(0, 255, 0)), tmp_path / "a.png")
    out = key_to_alpha(src, tmp_path / "b.png", key=(0, 255, 0), tolerance=30)
    assert out.key == (0, 255, 0)
    assert out.tolerance == 30


# ------------------------------------------------------- edge colour detection

def test_dominant_edge_colour_finds_the_background(tmp_path):
    src = write(keyed_image(key=(10, 200, 30)), tmp_path / "a.png")
    assert dominant_edge_color(src) == (10, 200, 30)


def test_dominant_edge_colour_ignores_the_centre(tmp_path):
    """It samples the border; a large subject must not win the vote."""
    im = Image.new("RGB", (64, 64), (5, 5, 5))
    for x in range(2, 62):
        for y in range(2, 62):
            im.putpixel((x, y), SUBJECT)
    src = write(im, tmp_path / "a.png")
    assert dominant_edge_color(src, border=1) == (5, 5, 5)


# -------------------------------------------------------------------- trimming

def test_trim_crops_transparent_margins_to_the_subject(tmp_path):
    src = write(keyed_image(size=(64, 64), box=(16, 16, 48, 48)), tmp_path / "a.png")
    keyed = key_to_alpha(src, tmp_path / "k.png")

    # Exactly the subject, with no padding: 64x64 down to the 32x32 subject.
    trimmed = trim_to_content(keyed.path, tmp_path / "t.png", padding=0)
    assert Image.open(trimmed).size == (32, 32)


def test_trim_keeps_the_requested_padding(tmp_path):
    """The default leaves an 8px margin, so the subject does not touch the edge."""
    src = write(keyed_image(size=(64, 64), box=(16, 16, 48, 48)), tmp_path / "a.png")
    keyed = key_to_alpha(src, tmp_path / "k.png")

    trimmed = trim_to_content(keyed.path, tmp_path / "t.png", padding=8)
    assert Image.open(trimmed).size == (48, 48)


def test_trim_padding_is_clamped_to_the_image(tmp_path):
    """Padding must not ask for pixels outside the source."""
    src = write(keyed_image(size=(64, 64), box=(2, 2, 62, 62)), tmp_path / "a.png")
    keyed = key_to_alpha(src, tmp_path / "k.png")

    trimmed = trim_to_content(keyed.path, tmp_path / "t.png", padding=40)
    assert Image.open(trimmed).size == (64, 64)


def test_trim_leaves_a_full_bleed_image_alone(tmp_path):
    src = write(Image.new("RGBA", (24, 24), (*SUBJECT, 255)), tmp_path / "a.png")
    assert Image.open(trim_to_content(src, tmp_path / "t.png")).size == (24, 24)
