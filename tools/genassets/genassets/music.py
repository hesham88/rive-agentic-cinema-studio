"""Music engine — generated score and sound design for a Rive scene.

Lyria returns MP3, and Rive's `upload_asset` accepts mp3/wav/flac directly, so
audio is the one Gemini output that reaches Rive with no format surgery at all.
Compare image (raster, needs tracing) and video (no path into Rive whatsoever).

Two things this module knows that are not obvious:

  * Lyria emits a **structure map** alongside the audio — a text part like
    `[[A0]] [[A1]] [[B2]]` naming song sections. That is a timing outline, and
    it is what lets a cue be matched to a shot list rather than laid under it
    arbitrarily.
  * A generated cue is **large**. The first launch cue came back at 2.6 MB, which
    is 70x the whole visual scene. Audio dominates the payload of any Rive file
    that carries it, so duration and reuse are budget decisions, not details.
  * **Lyria ignores the requested duration.** A prompt asking for 5 seconds
    returned 59.2 s. Length is flavour to the model, not instruction, so a cue
    must be trimmed after generation or reused across a long enough sequence to
    justify its bytes. `seconds` in `build_prompt` shapes the *character* of the
    piece (a "5-second cue" reads as terse), not its length.
  * Uploaded audio arrives with **`includeInExport: false`**, exactly like fonts
    and non-default artboards. Authoring an asset does not ship it.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["MusicEngine", "MusicError", "Cue", "CUE_STYLES", "describe_shots"]

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "lyria-3-pro-preview"

# Rive accepts these directly (verified from upload_asset's own description).
RIVE_AUDIO_FORMATS = {"mp3", "wav", "flac"}

_MIME_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}

_SECTION_RE = re.compile(r"\[\[([A-Za-z]+)(\d+)\]\]")


class MusicError(RuntimeError):
    pass


@dataclass
class Cue:
    """A generated piece of music and what is known about its shape."""

    path: pathlib.Path
    mime_type: str
    bytes_len: int
    prompt: str
    #: Section labels Lyria reported, e.g. [("A", 0), ("A", 1), ("B", 2)].
    sections: list[tuple[str, int]] = field(default_factory=list)

    @property
    def extension(self) -> str:
        """File extension for this cue.

        Rive detects AUDIO type from the filename extension — unlike images and
        fonts, which it sniffs from content. So the extension is load-bearing,
        not cosmetic: a `.ogg` named `.mp3` will be accepted and then fail.
        """
        known = _MIME_EXT.get(self.mime_type)
        if known:
            return known
        # Unlabelled or novel mime: fall back to the format Lyria has always
        # returned, rather than inventing an extension from the mime string.
        return "mp3" if self.mime_type.startswith("audio/") else "bin"

    @property
    def rive_compatible(self) -> bool:
        """True only when the mime is one Rive actually accepts.

        Checked against the MIME, not the defaulted extension — otherwise the
        mp3 fallback would quietly mark an unsupported format as compatible and
        the failure would surface later, inside the editor.
        """
        return _MIME_EXT.get(self.mime_type) in RIVE_AUDIO_FORMATS

    @property
    def megabytes(self) -> float:
        return self.bytes_len / (1024 * 1024)

    def section_summary(self) -> str:
        if not self.sections:
            return "no section markers"
        letters = [s for s, _ in self.sections]
        return f"{len(self.sections)} sections: {' '.join(letters)}"


# Cue styles as director's language rather than synth settings. Each is written
# to be sung back into a prompt, so the model gets intent instead of parameters.
CUE_STYLES: dict[str, str] = {
    "cinematic-rise": (
        "sparse and hopeful, a slow rising swell, warm analogue pad with a "
        "distant shimmer, no drums until the final third"
    ),
    "playful-ui": (
        "light and rhythmic, short plucked notes, a friendly major key, "
        "the feel of a well-made interface responding"
    ),
    "tension": (
        "low sustained strings, a slow pulse that tightens, minimal melody, "
        "space left for sound effects"
    ),
    "wonder": (
        "airy and wide, bell-like tones over a soft drone, unhurried, "
        "the feeling of seeing something for the first time"
    ),
    "resolve": (
        "warm and settled, a simple descending motif, gentle close, "
        "the sound of something finishing well"
    ),
}


def describe_shots(shots: list[tuple[str, int]], *, fps: int = 60) -> str:
    """Turn a camera shot list into musical direction.

    The camera engine already knows the beats of a scene — where the push-in
    lands, how long the shake is, when the wide returns. Feeding that timing to
    the music model is what makes a cue fit the picture instead of merely
    playing under it.
    """
    if not shots:
        return ""
    lines = []
    t = 0.0
    for name, frames in shots:
        start, end = t, t + frames / fps
        lines.append(f"  {start:0.1f}s-{end:0.1f}s: {name.replace('-', ' ')}")
        t = end
    return f"The music accompanies this sequence, total {t:0.1f}s:\n" + "\n".join(lines)


class MusicEngine:
    """Generates cues with Lyria and prepares them for Rive."""

    def __init__(self, api_key: str | None = None, *, timeout: int = 300,
                 out_dir: str | pathlib.Path | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise MusicError("GEMINI_API_KEY is not set (see .env.example)")
        self._key = key
        self.timeout = timeout
        self.out_dir = pathlib.Path(
            out_dir or pathlib.Path(__file__).resolve().parents[3] / "assets" / "audio"
        )
        self.calls: list[dict] = []

    # ------------------------------------------------------------------ prompts

    @staticmethod
    def build_prompt(
        mood: str,
        *,
        style: str | None = None,
        seconds: int = 20,
        shot_notes: str = "",
        instrumental: bool = True,
    ) -> str:
        parts = [f"Compose a {seconds}-second cue: {mood}."]
        if style and style in CUE_STYLES:
            parts.append(CUE_STYLES[style] + ".")
        elif style:
            parts.append(style + ".")
        if shot_notes:
            parts.append(shot_notes)
        if instrumental:
            # Vocals fight with UI and dialogue, and cannot be looped cleanly.
            parts.append("Instrumental only, no vocals, no lyrics.")
        parts.append(
            "Leave headroom — this plays under an animation, not in front of it."
        )
        return "\n".join(parts)

    # --------------------------------------------------------------- generation

    def generate(
        self,
        mood: str,
        name: str,
        *,
        style: str | None = "cinematic-rise",
        seconds: int = 20,
        shot_notes: str = "",
    ) -> Cue:
        """Generate one cue and write it to disk."""
        prompt = self.build_prompt(mood, style=style, seconds=seconds,
                                   shot_notes=shot_notes)
        url = f"{API_ROOT}/models/{MODEL}:generateContent?key={self._key}"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()[:400].decode("utf-8", "replace")
            raise MusicError(f"lyria -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise MusicError(f"lyria -> network error: {e.reason}") from e

        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise MusicError(f"unexpected response: {json.dumps(data)[:300]}") from e

        audio: bytes | None = None
        mime = ""
        sections: list[tuple[str, int]] = []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                audio = base64.b64decode(inline["data"])
                mime = inline.get("mimeType", "audio/mpeg")
            elif part.get("text"):
                sections.extend(
                    (m.group(1), int(m.group(2)))
                    for m in _SECTION_RE.finditer(part["text"])
                )

        if audio is None:
            raise MusicError("response contained no audio")

        ext = _MIME_EXT.get(mime, "mp3")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{name}.{ext}"
        path.write_bytes(audio)

        self.calls.append({
            "name": name, "seconds_requested": seconds,
            "bytes": len(audio), "elapsed": round(time.time() - t0, 1),
        })
        return Cue(path=path, mime_type=mime, bytes_len=len(audio),
                   prompt=prompt, sections=sections)

    # -------------------------------------------------------------------- Rive

    def attach_to_rive(self, cue: Cue, *, mcp=None) -> dict:
        """Upload a cue into the open Rive file as an audio asset.

        Returns the asset metadata. Raises if the format is not one Rive takes,
        rather than uploading something the editor will reject later.
        """
        if not cue.rive_compatible:
            raise MusicError(
                f"{cue.path.name} is {cue.extension}; Rive accepts "
                f"{sorted(RIVE_AUDIO_FORMATS)}"
            )
        if mcp is None:
            from .rivemcp import RiveMCP

            mcp = RiveMCP()
        # The parameter is `file`, and for audio the PATH's extension is what
        # Rive uses to detect the type — it does not sniff audio content.
        return mcp.call("upload_asset", {"file": str(cue.path.resolve())})
