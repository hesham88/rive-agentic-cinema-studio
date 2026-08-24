"""Colour counting and image classification.

The regression these guard: `count_colors` once downsampled with LANCZOS, which
interpolates. A quantized 12-colour image counted as 469 colours, was classified
as a photograph, and the vectorizer refused it — so the whole pipeline failed on
exactly the flat art it is designed for.
"""

import numpy as np
import pytest
from PIL import Image

from genassets.normalize import count_colors, normalize, sniff_format
from genassets.vectorize import ImageClass, classify


def flat_image(colors: list[tuple[int, int, int]], size: int = 512) -> Image.Image:
    """An image of hard-edged vertical bands — no gradients anywhere.

    Bands are computed so they tile the full width exactly. An integer-division
    band width leaves a remainder strip of the initialisation colour, which
    silently adds a phantom extra colour to every count.
    """
    a = np.zeros((size, size, 3), dtype=np.uint8)
    n = len(colors)
    for i, c in enumerate(colors):
        start = (i * size) // n
        end = ((i + 1) * size) // n
        a[:, start:end] = c
    return Image.fromarray(a, "RGB")


def gradient_image(size: int = 512) -> Image.Image:
    """A smooth gradient — genuinely continuous tone."""
    x = np.linspace(0, 255, size, dtype=np.uint8)
    a = np.stack([np.tile(x, (size, 1))] * 3, axis=-1)
    return Image.fromarray(a.astype(np.uint8), "RGB")


class TestCountColors:
    def test_counts_a_flat_image_exactly(self):
        # THE REGRESSION. Under LANCZOS this returned hundreds.
        im = flat_image([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        assert count_colors(im) == 3

    def test_twelve_flat_colors_count_as_twelve(self):
        colors = [(i * 20, 255 - i * 20, 128) for i in range(12)]
        assert count_colors(flat_image(colors)) == 12

    def test_a_gradient_counts_as_many(self):
        assert count_colors(gradient_image()) > 100

    def test_a_single_colour_counts_as_one(self):
        assert count_colors(flat_image([(17, 34, 51)])) == 1


class TestClassify:
    def test_flat_art_classifies_flat(self):
        assert classify(count_colors(flat_image([(255, 0, 0), (0, 0, 255)]))) is ImageClass.FLAT

    def test_twelve_colours_classify_flat_not_photo(self):
        # The exact case the agent hit: a quantized 12-colour icon.
        colors = [(i * 20, 255 - i * 20, 128) for i in range(12)]
        assert classify(count_colors(flat_image(colors))) is ImageClass.FLAT

    def test_a_gradient_classifies_photo(self):
        assert classify(count_colors(gradient_image())) is ImageClass.PHOTO

    def test_thresholds_are_inclusive_at_the_boundaries(self):
        assert classify(24) is ImageClass.FLAT
        assert classify(25) is ImageClass.ILLUSTRATION
        assert classify(220) is ImageClass.ILLUSTRATION
        assert classify(221) is ImageClass.PHOTO


class TestNormalize:
    def test_jpeg_is_detected_by_content_not_extension(self, tmp_path):
        # Gemini returns JPEG bytes whatever the filename.
        src = tmp_path / "misnamed.png"
        flat_image([(200, 30, 30), (30, 30, 200)]).save(src, "JPEG", quality=90)
        assert sniff_format(src.read_bytes()) == "JPEG"

        out = normalize(src, tmp_path / "out.png")
        assert out.source_format == "JPEG"
        assert out.was_jpeg
        assert sniff_format(out.path.read_bytes()) == "PNG"

    def test_quantization_collapses_jpeg_artifacts(self, tmp_path):
        # JPEG ringing around hard edges inflates the colour count; quantizing
        # collapses it back so the image classifies as the flat art it is.
        src = tmp_path / "art.png"
        flat_image([(220, 40, 40), (40, 180, 90), (30, 60, 200)]).save(
            src, "JPEG", quality=70
        )

        noisy = normalize(src, tmp_path / "noisy.png")
        clean = normalize(src, tmp_path / "clean.png", quantize_colors=8)

        assert clean.quantized is True
        assert clean.color_count <= 8
        assert clean.color_count < noisy.color_count
        assert classify(clean.color_count) is ImageClass.FLAT

    def test_unrecognised_bytes_are_rejected(self, tmp_path):
        bad = tmp_path / "nope.png"
        bad.write_bytes(b"definitely not an image")
        with pytest.raises(ValueError, match="unrecognized image format"):
            normalize(bad, tmp_path / "out.png")
