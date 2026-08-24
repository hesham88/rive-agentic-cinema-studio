"""Gemini client for asset generation and editing.

One client for every call, so metering and the spend cap exist once rather than
being reimplemented per feature. Generation is the only part of this project that
costs money per run (BIBLE: the ledger exists from the first call, not retrofitted).

Verified live on 2026-08-23 — all four models exist on the owner's key:
    gemini-3.1-flash-image    (Nano Banana 2)  generateContent   image gen + edit
    gemini-omni-flash-preview                  generateContent   multimodal reasoning
    veo-3.1-generate-preview                   predictLongRunning  video (async, poll)
    lyria-3-pro-preview                        generateContent   music

Note: image responses come back as **JPEG** whatever you name the file. Always
pass the result through normalize.py before tracing.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import pathlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["GeminiClient", "GeminiError", "SpendCapExceeded", "Models", "Ledger"]

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(RuntimeError):
    pass


class SpendCapExceeded(GeminiError):
    pass


class Models:
    IMAGE = "gemini-3.1-flash-image"
    OMNI = "gemini-omni-flash-preview"
    TEXT = "gemini-2.5-flash"
    VIDEO = "veo-3.1-generate-preview"
    MUSIC = "lyria-3-pro-preview"


@dataclass
class Ledger:
    """Call log plus a hard cap checked BEFORE each request."""

    max_calls: int = 100
    calls: list[dict] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.calls)

    def check(self) -> None:
        if self.count >= self.max_calls:
            raise SpendCapExceeded(
                f"call cap reached ({self.max_calls}). Raise max_calls deliberately."
            )

    def record(self, model: str, kind: str, seconds: float, out_bytes: int) -> None:
        self.calls.append(
            {"model": model, "kind": kind, "seconds": round(seconds, 2), "bytes": out_bytes}
        )

    def summary(self) -> str:
        if not self.calls:
            return "no calls"
        total = sum(c["seconds"] for c in self.calls)
        by_model: dict[str, int] = {}
        for c in self.calls:
            by_model[c["model"]] = by_model.get(c["model"], 0) + 1
        parts = ", ".join(f"{m}x{n}" for m, n in sorted(by_model.items()))
        return f"{self.count} calls, {total:.1f}s total ({parts})"


class GeminiClient:
    def __init__(self, api_key: str | None = None, *, ledger: Ledger | None = None,
                 timeout: int = 180):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY is not set (see .env, which is gitignored)")
        self._key = key
        self.ledger = ledger or Ledger()
        self.timeout = timeout

    # ---------------------------------------------------------------- transport

    def _post(self, model: str, method: str, payload: dict) -> dict:
        self.ledger.check()
        url = f"{API_ROOT}/models/{model}:{method}?key={self._key}"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()[:400].decode("utf-8", "replace")
            raise GeminiError(f"{model} {method} -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise GeminiError(f"{model} {method} -> network error: {e.reason}") from e
        self.ledger.record(model, method, time.time() - t0, len(json.dumps(body)))
        return body

    @staticmethod
    def _parts(response: dict) -> list[dict]:
        try:
            return response["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise GeminiError(f"unexpected response shape: {json.dumps(response)[:300]}") from e

    @classmethod
    def _first_inline(cls, response: dict) -> tuple[bytes, str]:
        for part in cls._parts(response):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"]), inline.get("mimeType", "")
        raise GeminiError("response contained no inline media")

    @classmethod
    def _text(cls, response: dict) -> str:
        return "".join(p.get("text", "") for p in cls._parts(response))

    @staticmethod
    def _image_part(path: str | pathlib.Path) -> dict:
        p = pathlib.Path(path)
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return {"inlineData": {"mimeType": mime, "data": base64.b64encode(p.read_bytes()).decode()}}

    # ------------------------------------------------------------------ images

    def generate_image(self, prompt: str, out: str | pathlib.Path,
                       *, model: str = Models.IMAGE) -> pathlib.Path:
        """Text -> image. Output is JPEG bytes; normalize before tracing."""
        data, _ = self._first_inline(
            self._post(model, "generateContent", {"contents": [{"parts": [{"text": prompt}]}]})
        )
        out = pathlib.Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return out

    def edit_image(self, image: str | pathlib.Path, instruction: str,
                   out: str | pathlib.Path, *, model: str = Models.IMAGE) -> pathlib.Path:
        """Image + instruction -> edited image. The basis of the two helpers below."""
        payload = {"contents": [{"parts": [self._image_part(image), {"text": instruction}]}]}
        data, _ = self._first_inline(self._post(model, "generateContent", payload))
        out = pathlib.Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return out

    def remove_background(self, image, out, *, model: str = Models.IMAGE) -> pathlib.Path:
        """Isolate the subject on a flat, uniform background.

        Deliberately asks for a FLAT KEY COLOR rather than transparency: the model
        returns JPEG, which has no alpha channel, so "make it transparent" yields
        an arbitrary matte. A known key color can be made transparent losslessly
        afterwards (see cutout.key_to_alpha), and it also traces cleanly — the
        background collapses to exactly one path.
        """
        return self.edit_image(
            image,
            "Remove the background completely. Keep the main subject exactly as it is, "
            "unchanged in color, shape, and detail. Replace the entire background with a "
            "single flat solid magenta (#FF00FF) fill, edge to edge, with no gradient, "
            "no shadow, no vignette, and no texture. Do not add any new elements.",
            out,
            model=model,
        )

    def remove_object(self, image, description: str, out,
                      *, model: str = Models.IMAGE) -> pathlib.Path:
        """Erase a named object and inpaint plausibly behind it."""
        return self.edit_image(
            image,
            f"Remove the {description} from this image completely. Reconstruct whatever "
            f"should be behind it so the result looks natural and seamless, matching the "
            f"surrounding lighting, texture, and perspective. Change nothing else.",
            out,
            model=model,
        )

    def flatten_for_tracing(self, image, out, *, colors: int = 8,
                            model: str = Models.IMAGE) -> pathlib.Path:
        """Re-render as flat vector-style art.

        The most effective way to make a photographic or painterly source
        traceable: rather than fighting the tracer's settings, ask the image model
        to redraw the subject as flat art, which vectorizes cleanly.
        """
        return self.edit_image(
            image,
            f"Redraw this as flat vector-style illustration using at most {colors} flat "
            f"solid colors. Hard edges, no gradients, no shading, no texture, no noise, "
            f"no drop shadows. Preserve the subject's shape, proportions, and layout.",
            out,
            model=model,
        )

    # ------------------------------------------------------------------- other

    def generate_svg(self, subject: str, *, max_paths: int = 20,
                     model: str = Models.TEXT) -> str:
        """Route A: ask for SVG markup directly.

        NICHE ONLY. The spike found this wins on every metric (4 paths, 0.4 KB) and
        loses on the only one that matters — it drew a lopsided non-airplane and a
        brown blob. Use for trivial geometry (bars, rings, arrows); trace anything
        that has to look like something.
        """
        prompt = (
            "Output ONLY valid SVG markup, no markdown fence, no commentary. "
            "A single <svg> root with an explicit viewBox; only <path> elements with flat "
            f"`fill` colors; no gradients, filters, <image>, CSS, or embedded raster; under "
            f"{max_paths} paths.\nSubject: {subject}"
        )
        text = self._text(self._post(model, "generateContent",
                                     {"contents": [{"parts": [{"text": prompt}]}]}))
        start, end = text.find("<svg"), text.rfind("</svg>")
        if start < 0 or end < 0:
            raise GeminiError("no <svg> element in response")
        return text[start:end + len("</svg>")]

    def describe_image(self, image, question: str, *, model: str = Models.OMNI) -> str:
        """Multimodal read of an image — critique, style extraction, QA."""
        payload = {"contents": [{"parts": [self._image_part(image), {"text": question}]}]}
        return self._text(self._post(model, "generateContent", payload))

    def generate_music(self, prompt: str, out: str | pathlib.Path,
                       *, model: str = Models.MUSIC) -> pathlib.Path:
        """Text -> audio. Rive ingests audio assets directly (decodeAudio)."""
        data, _ = self._first_inline(
            self._post(model, "generateContent", {"contents": [{"parts": [{"text": prompt}]}]})
        )
        out = pathlib.Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return out

    def generate_video(self, prompt: str, *, model: str = Models.VIDEO,
                       poll_seconds: int = 10, max_wait: int = 600) -> dict:
        """Text -> video. Uses predictLongRunning, so it must be polled.

        Video has NO path into a .riv (Rive does not play video). Its honest uses
        are rotoscoping reference, a composite web layer, and marketing.
        """
        op = self._post(model, "predictLongRunning",
                        {"instances": [{"prompt": prompt}]})
        name = op.get("name")
        if not name:
            raise GeminiError(f"no operation name in response: {json.dumps(op)[:200]}")

        deadline = time.time() + max_wait
        while time.time() < deadline:
            req = urllib.request.Request(f"{API_ROOT}/{name}?key={self._key}")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                status = json.load(r)
            if status.get("done"):
                return status
            time.sleep(poll_seconds)
        raise GeminiError(f"video operation {name} did not complete within {max_wait}s")
