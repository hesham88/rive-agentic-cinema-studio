"""Watch YouTube videos with Gemini and take craft notes.

Why this exists
---------------
The reference material for this project includes Rive's video tutorials and
playlists. YouTube pages are JavaScript-rendered, so no amount of HTML fetching
gets at the content — the technique is *in the video*, and there is no transcript
endpoint to scrape.

Gemini accepts a YouTube URL directly as `file_data`, watches the video, and can
be asked structured questions about it. That is a real capability, not a
workaround: it reads the screen recording of an editor, so it can report which
panel was clicked and what value was typed — which is exactly the detail the
prose docs omit.

Notes are written as markdown, one file per video, and cached: re-running skips
videos already transcribed so a long playlist can be resumed.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

__all__ = ["VideoNoteTaker", "NoteError", "CRAFT_PROMPT", "youtube_id"]

API = "https://generativelanguage.googleapis.com/v1beta/models"

#: Default model. Video understanding needs a large context and native video
#: input; flash is fast enough for a playlist and cheap enough to run over dozens
#: of tutorials. Verify against ListModels before changing — several plausible
#: ids (gemini-3.1-flash) simply do not exist and 404 at generateContent.
DEFAULT_MODEL = "gemini-3.7-flash"


class NoteError(RuntimeError):
    pass


def youtube_id(url: str) -> str | None:
    """Extract a video id from any common YouTube URL shape."""
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


#: What to ask about a Rive tutorial.
#:
#: Deliberately demands specifics — panel names, numeric values, the order of
#: operations — because a summary of "they made a button" teaches nothing. The
#: last section is the important one: it forces the model to say what it could
#: NOT determine, so the notes never read as more authoritative than they are.
CRAFT_PROMPT = """You are taking engineering notes on a Rive tutorial for a team
building a generative Rive pipeline. Watch the whole video.

Report, using headings:

1. **What is built** — one paragraph.
2. **Editor operations, in order** — the actual clicks: which tool, which panel,
   which property, which value typed. Name properties exactly as the Inspector
   shows them.
3. **Rive features used** — state machine layers, blend states (1D/additive),
   listeners, trim path, meshes, bones, constraints, joysticks, solos,
   components/nested artboards, data binding, converters, text modifiers,
   scripting. For each, say HOW it was configured.
4. **Animation craft** — timing in frames or seconds, easing choices,
   anticipation/overshoot/follow-through, arcs, squash and stretch, staging.
   Give numbers wherever they are visible on screen.
5. **Anything counter-intuitive** — gotchas, defaults that had to be changed,
   things the presenter warned about.
6. **What I could not determine** — be explicit about anything unclear, offscreen
   or too fast to read. Do not guess.

Be concrete and technical. Prefer exact values over description."""


@dataclass
class Note:
    video_id: str
    url: str
    title: str
    path: Path


class VideoNoteTaker:
    """Transcribes and analyses videos into markdown notes."""

    def __init__(self, out_dir: str | Path, *, api_key: str | None = None,
                 model: str = DEFAULT_MODEL, verbose: bool = True):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise NoteError("GEMINI_API_KEY is not set (see .env, which is gitignored)")
        self._key = key
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  {msg}", flush=True)

    def _generate(self, url: str, prompt: str, *, retries: int = 3) -> str:
        body = {
            "contents": [{
                "parts": [
                    {"file_data": {"file_uri": url}},
                    {"text": prompt},
                ]
            }],
            # Low temperature: these are notes, not prose. Invention is the
            # failure mode we care about.
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
        }
        endpoint = f"{API}/{self.model}:generateContent?key={self._key}"
        last: Exception | None = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = json.loads(r.read().decode())
                cands = data.get("candidates") or []
                if not cands:
                    raise NoteError(f"no candidates: {json.dumps(data)[:300]}")
                parts = cands[0].get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts).strip()
                if not text:
                    raise NoteError("empty response")
                return text
            except urllib.error.HTTPError as e:
                detail = e.read().decode()[:300]
                last = NoteError(f"HTTP {e.code}: {detail}")
                # 4xx other than rate-limit will not fix themselves.
                if e.code not in (429, 500, 502, 503, 504):
                    raise last
            except Exception as e:  # noqa: BLE001 - retry any transport failure
                last = e
            wait = 4 * (attempt + 1)
            self._log(f"retry in {wait}s ({last})")
            time.sleep(wait)
        raise NoteError(f"failed after {retries} attempts: {last}")

    def note(self, url: str, *, prompt: str = CRAFT_PROMPT,
             force: bool = False) -> Note:
        vid = youtube_id(url) or re.sub(r"\W+", "-", url)[-40:]
        path = self.out_dir / f"{vid}.md"
        if path.exists() and not force:
            self._log(f"cached {vid}")
            return Note(vid, url, path.stem, path)

        self._log(f"watching {vid} …")
        text = self._generate(url, prompt)
        header = f"# {vid}\n\nSource: {url}\nModel: {self.model}\n\n---\n\n"
        path.write_text(header + text, encoding="utf-8")
        self._log(f"wrote {path.name} ({len(text)} chars)")
        return Note(vid, url, path.stem, path)

    def note_all(self, urls: list[str], *, prompt: str = CRAFT_PROMPT,
                 force: bool = False) -> list[Note]:
        notes: list[Note] = []
        for i, u in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {u}", flush=True)
            try:
                notes.append(self.note(u, prompt=prompt, force=force))
            except Exception as e:  # noqa: BLE001 - one bad video must not stop a playlist
                print(f"  FAILED: {str(e)[:200]}", flush=True)
        return notes
