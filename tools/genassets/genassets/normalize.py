"""Image normalization — the step that makes everything downstream work.

Gemini returns **JPEG bytes regardless of the filename** you save them under.
Two things break because of that:

1. `vtracer` keys on the file extension and fails with the misleading error
   "No image file found at specified input path" on a file that plainly exists.
2. JPEG is lossy, and its ringing artifacts around hard edges become spurious
   paths and colors. Measured: a 4-color source traced to **46 colors**.

So every image entering the pipeline is decoded by content (never by extension),
re-encoded as a true PNG, and optionally quantized to collapse artifact colors
back into the flat regions they came from.
"""

from __future__ import annotations

import io
import pathlib
from dataclasses import dataclass

from PIL import Image

__all__ = ["NormalizedImage", "sniff_format", "normalize"]

# Magic numbers — content, not extension, decides the format.
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"BM", "BMP"),
]


@dataclass(frozen=True)
class NormalizedImage:
    path: pathlib.Path
    source_format: str
    size: tuple[int, int]
    color_count: int
    quantized: bool

    @property
    def was_jpeg(self) -> bool:
        return self.source_format == "JPEG"


def sniff_format(data: bytes) -> str:
    """Identify an image format from its magic bytes, ignoring any filename."""
    for magic, name in _MAGIC:
        if data.startswith(magic):
            return name
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return "UNKNOWN"


def count_colors(im: Image.Image, *, sample: int = 256) -> int:
    """Approximate distinct colors, downsampled so the cost is bounded.

    Used to classify an image (flat art vs illustration vs photo).

    **Resampling MUST be NEAREST.** A smooth filter (LANCZOS, BILINEAR) blends
    neighbouring pixels, so every hard edge between two flat colours becomes a
    gradient of invented intermediate values. Measured: a quantized 12-colour
    image counted as 469 colours under LANCZOS and was misclassified as a
    photograph, which made the vectorizer refuse it. NEAREST samples real
    pixels, which is what a colour census needs.
    """
    small = im.convert("RGB")
    small.thumbnail((sample, sample), Image.Resampling.NEAREST)
    colors = small.getcolors(maxcolors=sample * sample)
    return len(colors) if colors else sample * sample


def normalize(
    src: str | pathlib.Path,
    dst: str | pathlib.Path,
    *,
    quantize_colors: int | None = None,
    max_dimension: int | None = 2048,
) -> NormalizedImage:
    """Decode `src` by content and write a true PNG to `dst`.

    quantize_colors: collapse to at most N colors before tracing. This is the
        single most effective artifact suppressor for JPEG sources — it merges
        the ringing halo back into the flat region it surrounds.
    max_dimension: downscale the long edge. Tracing cost scales with pixel
        count, and detail beyond ~2048px rarely survives vectorization anyway.
    """
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    data = src.read_bytes()
    fmt = sniff_format(data)
    if fmt == "UNKNOWN":
        raise ValueError(f"{src.name}: unrecognized image format (first bytes: {data[:8]!r})")

    im = Image.open(io.BytesIO(data))
    im.load()
    im = im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")

    if max_dimension and max(im.size) > max_dimension:
        im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    quantized = False
    if quantize_colors:
        # Quantize on RGB, then restore alpha, so transparency survives.
        alpha = im.getchannel("A") if im.mode == "RGBA" else None
        q = im.convert("RGB").quantize(colors=quantize_colors, method=Image.Quantize.MEDIANCUT)
        im = q.convert("RGB")
        if alpha is not None:
            im = im.convert("RGBA")
            im.putalpha(alpha)
        quantized = True

    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "PNG", optimize=True)

    return NormalizedImage(
        path=dst,
        source_format=fmt,
        size=im.size,
        color_count=count_colors(im),
        quantized=quantized,
    )
