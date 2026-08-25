"""Tests for the normalization step.

`normalize.py` documents the pipeline's most expensive finding — Gemini returns
JPEG whatever you name the file, and the resulting ringing turned a 4-colour
source into 46 traced colours — and had no tests. A documented finding with no
test is a comment; the next refactor is free to undo it.
"""
from __future__ import annotations

import io
import pathlib

import pytest
from PIL import Image

from genassets.normalize import count_colors, normalize, sniff_format


def flat_image(colors: int = 4, size: tuple[int, int] = (64, 64)) -> Image.Image:
    """An image of N vertical bands of flat colour — no gradients anywhere."""
    im = Image.new("RGB", size)
    px = im.load()
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
               (255, 0, 255), (0, 255, 255), (0, 0, 0), (255, 255, 255)]
    band = max(1, size[0] // colors)
    for x in range(size[0]):
        for y in range(size[1]):
            px[x, y] = palette[min(x // band, colors - 1)]
    return im


def write(im: Image.Image, path: pathlib.Path, fmt: str) -> pathlib.Path:
    im.save(path, fmt)
    return path


# ------------------------------------------------------------------- sniffing

def test_sniffs_jpeg_by_content_not_extension(tmp_path):
    """The whole point: a JPEG saved as `.png` must still read as JPEG."""
    lying = tmp_path / "actually-a-jpeg.png"
    flat_image().save(lying, "JPEG")
    assert sniff_format(lying.read_bytes()) == "JPEG"


def test_sniffs_png(tmp_path):
    p = write(flat_image(), tmp_path / "a.png", "PNG")
    assert sniff_format(p.read_bytes()) == "PNG"


def test_sniffs_webp(tmp_path):
    p = write(flat_image(), tmp_path / "a.webp", "WEBP")
    assert sniff_format(p.read_bytes()) == "WEBP"


def test_unrecognised_bytes_are_named_as_such():
    assert sniff_format(b"this is not an image at all") == "UNKNOWN"


def test_normalize_refuses_a_non_image(tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_bytes(b"just some prose")
    with pytest.raises(ValueError, match="unrecognized image format"):
        normalize(junk, tmp_path / "out.png")


# ------------------------------------------------------------- re-encoding

def test_a_jpeg_source_is_written_out_as_a_real_png(tmp_path):
    """vtracer keys on the extension; the bytes must match the name."""
    src = tmp_path / "from-gemini.png"
    flat_image().save(src, "JPEG")

    out = normalize(src, tmp_path / "clean.png")

    assert out.source_format == "JPEG"
    assert out.was_jpeg
    assert sniff_format(out.path.read_bytes()) == "PNG"


def test_reports_png_sources_as_png(tmp_path):
    src = write(flat_image(), tmp_path / "a.png", "PNG")
    out = normalize(src, tmp_path / "b.png")
    assert out.source_format == "PNG"
    assert not out.was_jpeg


def test_downscales_past_the_max_dimension(tmp_path):
    src = write(flat_image(size=(4000, 1000)), tmp_path / "big.png", "PNG")
    out = normalize(src, tmp_path / "small.png", max_dimension=512)
    assert max(out.size) == 512


def test_leaves_a_small_image_alone(tmp_path):
    src = write(flat_image(size=(100, 50)), tmp_path / "s.png", "PNG")
    out = normalize(src, tmp_path / "o.png", max_dimension=2048)
    assert out.size == (100, 50)


# ------------------------------------------------------------------ quantizing

def test_quantizing_collapses_jpeg_ringing_back_to_flat_colours(tmp_path):
    """The measured finding: a 4-colour source traced to 46 colours.

    Saving flat bands as a low-quality JPEG invents intermediate colours around
    every hard edge. Quantizing must merge them back.
    """
    src = tmp_path / "ringing.png"
    flat_image(colors=4, size=(256, 256)).save(src, "JPEG", quality=30)

    raw = normalize(src, tmp_path / "raw.png")
    assert raw.color_count > 4, "fixture is wrong: this JPEG has no artifacts to remove"

    fixed = normalize(src, tmp_path / "fixed.png", quantize_colors=4)
    assert fixed.quantized
    assert fixed.color_count <= 4
    assert fixed.color_count < raw.color_count


def test_quantizing_preserves_transparency(tmp_path):
    """Quantize runs on RGB; alpha has to be put back or cutouts turn opaque."""
    im = flat_image(colors=4).convert("RGBA")
    im.putalpha(Image.new("L", im.size, 128))
    src = tmp_path / "a.png"
    im.save(src, "PNG")

    out = normalize(src, tmp_path / "q.png", quantize_colors=4)

    result = Image.open(out.path)
    assert result.mode == "RGBA"
    assert result.getchannel("A").getextrema() == (128, 128)


def test_not_quantized_unless_asked(tmp_path):
    src = write(flat_image(), tmp_path / "a.png", "PNG")
    assert normalize(src, tmp_path / "b.png").quantized is False


# ------------------------------------------------------------- colour counting

def test_count_colors_uses_nearest_and_does_not_invent_colours():
    """Measured: a 12-colour image counted as 469 under LANCZOS, and was then
    misclassified as a photograph so the vectorizer refused it."""
    assert count_colors(flat_image(colors=4, size=(512, 512))) == 4


def test_count_colors_survives_an_image_smaller_than_the_sample():
    assert count_colors(flat_image(colors=2, size=(3, 3))) == 2
