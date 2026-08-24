"""Raster -> SVG, with the setting profile chosen per image class.

The spike (docs/superpowers/specs/2026-08-23-vectorizer-spike-findings.md) showed
that **one setting profile cannot serve all art**:

    icon  + FLAT profile  ->   5 paths, indistinguishable from source
    illus + FLAT profile  ->  15 paths, UNRECOGNIZABLE
    illus + COARSE profile ->  54 paths, excellent
    photo + any usable profile -> destroyed; only 5154 paths/5MB was faithful

So the pipeline classifies first and traces second. A fixed profile silently
ruins most inputs, which is worse than failing.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from enum import Enum

__all__ = ["ImageClass", "TraceResult", "classify", "PROFILES", "vectorize", "PathBudget"]


class ImageClass(str, Enum):
    FLAT = "flat"            # icons, logos, hard-edged vector-style art
    ILLUSTRATION = "illustration"  # multi-color flat/semi-flat illustration
    PHOTO = "photo"          # continuous tone — must NOT be vectorized


# vtracer settings per class, tuned against the spike fixtures.
PROFILES: dict[ImageClass, dict] = {
    ImageClass.FLAT: {
        "filter_speckle": 24, "color_precision": 3,
        "layer_difference": 32, "mode": "polygon",
    },
    ImageClass.ILLUSTRATION: {
        "filter_speckle": 16, "color_precision": 4, "path_precision": 4,
    },
    # Present for completeness. vectorize() refuses to use it — see below.
    ImageClass.PHOTO: {
        "filter_speckle": 8, "color_precision": 6,
    },
}

# Comfortable ceiling for an editable Rive artboard. The spike's illustration
# at 54 paths is fine; the photo at 5154 is not.
DEFAULT_MAX_PATHS = 150


class PathBudget(ValueError):
    """Raised when a trace exceeds the path ceiling Rive should carry."""


@dataclass(frozen=True)
class TraceResult:
    path: pathlib.Path
    image_class: ImageClass
    profile: str
    paths: int
    commands: int
    colors: int
    kb: float


def classify(color_count: int, *, flat_max: int = 24, illus_max: int = 220) -> ImageClass:
    """Classify by distinct-color count of the normalized image.

    Cheap and, on the spike fixtures, accurate: flat art collapses to a handful
    of colors, illustration to dozens, photographs to hundreds or thousands.
    """
    if color_count <= flat_max:
        return ImageClass.FLAT
    if color_count <= illus_max:
        return ImageClass.ILLUSTRATION
    return ImageClass.PHOTO


def measure_svg(text: str) -> dict:
    """Path/command/color counts — the numbers that decide Rive editability."""
    return {
        "paths": len(re.findall(r"<path\b", text)),
        "commands": sum(
            len(re.findall(r"[MLCQAZmlcqaz]", d))
            for d in re.findall(r'\bd="([^"]*)"', text)
        ),
        "colors": len(set(re.findall(r'fill="([^"]*)"', text))),
        "kb": len(text.encode()) / 1024,
    }


def vectorize(
    png: str | pathlib.Path,
    out_svg: str | pathlib.Path,
    *,
    image_class: ImageClass,
    max_paths: int = DEFAULT_MAX_PATHS,
    allow_photo: bool = False,
) -> TraceResult:
    """Trace a NORMALIZED png (see normalize.py) to SVG.

    Refuses photographs by default: the spike found no setting that both keeps a
    photo recognizable and stays inside a usable path count. Route C (import the
    raster as a bitmap asset) is the correct answer for those, not a fallback.
    """
    import vtracer  # imported lazily: a Rust extension, not needed to import this module

    png, out_svg = pathlib.Path(png), pathlib.Path(out_svg)
    if image_class is ImageClass.PHOTO and not allow_photo:
        raise PathBudget(
            "photographic images should not be vectorized — import as a bitmap asset "
            "(route C). Pass allow_photo=True only to reproduce the spike result."
        )

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    # vtracer's loader is happier with plain str paths than PathLike.
    vtracer.convert_image_to_svg_py(str(png), str(out_svg), **PROFILES[image_class])

    text = out_svg.read_text(encoding="utf-8")
    m = measure_svg(text)
    if m["paths"] > max_paths:
        raise PathBudget(
            f"trace produced {m['paths']} paths, over the {max_paths} ceiling. "
            f"Use a flatter profile, quantize harder, or import as a bitmap."
        )

    return TraceResult(
        path=out_svg,
        image_class=image_class,
        profile=str(PROFILES[image_class]),
        paths=m["paths"],
        commands=m["commands"],
        colors=m["colors"],
        kb=m["kb"],
    )
