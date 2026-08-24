"""Key-color -> alpha, and background flattening.

Why a key color rather than asking the model for transparency: Gemini returns
**JPEG**, which has no alpha channel. "Make the background transparent" therefore
produces an arbitrary matte — usually white or black — and the subject's edge
picks up a halo of it. Asking instead for a flat, saturated key color gives a
background that is:

  * removable losslessly here, with a tolerance that also catches JPEG ringing;
  * or traceable as exactly one path, if you keep it.

Magenta (#FF00FF) is the default key because it almost never occurs in natural
subject matter, so the tolerance can be generous without eating the subject.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import numpy as np
from PIL import Image

__all__ = ["CutoutResult", "key_to_alpha", "dominant_edge_color", "trim_to_content"]

DEFAULT_KEY = (255, 0, 255)


@dataclass(frozen=True)
class CutoutResult:
    path: pathlib.Path
    removed_fraction: float
    key: tuple[int, int, int]
    tolerance: int


def key_to_alpha(
    src: str | pathlib.Path,
    dst: str | pathlib.Path,
    *,
    key: tuple[int, int, int] = DEFAULT_KEY,
    tolerance: int = 90,
    despill: bool = True,
) -> CutoutResult:
    """Make every pixel near `key` transparent; write an RGBA PNG.

    tolerance is a Euclidean distance in RGB. It needs to be generous (~90) for
    JPEG sources, because compression smears the key color at the subject's edge.

    despill removes the key's color cast from surviving semi-transparent edge
    pixels — without it, a magenta key leaves a visible pink fringe.
    """
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im).astype(np.int16)

    rgb = arr[..., :3]
    dist = np.sqrt(((rgb - np.array(key, dtype=np.int16)) ** 2).sum(axis=-1))
    mask = dist <= tolerance

    out = arr.copy()
    out[..., 3] = np.where(mask, 0, out[..., 3])

    if despill:
        # Where a pixel survives but leans toward the key, pull the key's dominant
        # channels back toward the others. For magenta that kills the pink fringe.
        near = (~mask) & (dist <= tolerance * 2)
        if near.any():
            r, g, b = out[..., 0], out[..., 1], out[..., 2]
            if key == DEFAULT_KEY:  # magenta: R and B are the spill channels
                avg = ((r.astype(np.int32) + b.astype(np.int32)) // 2)
                fix = np.minimum(avg, g + 40)
                r[near] = np.minimum(r[near], fix[near])
                b[near] = np.minimum(b[near], fix[near])

    result = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(dst, "PNG", optimize=True)

    return CutoutResult(
        path=dst,
        removed_fraction=float(mask.mean()),
        key=key,
        tolerance=tolerance,
    )


def dominant_edge_color(src: str | pathlib.Path, *, border: int = 4) -> tuple[int, int, int]:
    """Most common color around the image border — the likely background.

    Useful when a source was not generated with a key color: sample the frame,
    then treat that color as the key.
    """
    im = Image.open(src).convert("RGB")
    a = np.asarray(im)
    edges = np.concatenate([
        a[:border].reshape(-1, 3), a[-border:].reshape(-1, 3),
        a[:, :border].reshape(-1, 3), a[:, -border:].reshape(-1, 3),
    ])
    colors, counts = np.unique(edges, axis=0, return_counts=True)
    return tuple(int(v) for v in colors[counts.argmax()])


def trim_to_content(src: str | pathlib.Path, dst: str | pathlib.Path,
                    *, padding: int = 8) -> pathlib.Path:
    """Crop transparent margins so the subject fills the artboard.

    Worth doing before import: Rive artboards are sized to their content, and a
    subject floating in a large transparent field wastes the artboard and makes
    every later transform harder to reason about.
    """
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    im = Image.open(src).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        x0, y0 = max(0, x0 - padding), max(0, y0 - padding)
        x1, y1 = min(im.width, x1 + padding), min(im.height, y1 + padding)
        im = im.crop((x0, y0, x1, y1))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "PNG", optimize=True)
    return dst
