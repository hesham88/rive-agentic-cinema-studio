"""Source openly-licensed vector art when generation is unavailable.

Why this exists
---------------
Image generation is metered and the credits run out. When they do the whole
pipeline stops, which makes a paid API a single point of failure for a project
whose point is that it runs on your own keys. This is the second source: real
SVGs that somebody already drew and licensed for reuse.

It is a genuine fallback rather than a lesser one, for a specific reason — these
are true vectors. There is no raster tracing step, so none of the quantisation
noise that makes a generated asset land at 84 near-duplicate colours.

What it will not do
-------------------
Match a house style. You get what exists. For a coherent set at the project's
Disney/Pixar standard the construction engine is the answer; this is for
breadth, reference, and keeping the pipeline alive.

Licensing is a hard gate, not a note
------------------------------------
Two rules, both enforced in code rather than documented and hoped for.

*Share-alike is rejected.* CC BY-SA is copyleft — using one SA-licensed shape in
a composite asset can oblige the whole work to be relicensed. This project is
MIT. An SA file is therefore not "attribution needed", it is unusable, and the
allowlist reflects that. NonCommercial and NoDerivatives are refused for the
same class of reason, and derivatives are exactly what this pipeline makes.

*Attribution is written or the file is not saved.* Same rule as `marketplace.py`
for the same reason: an asset that loses its provenance is a licence breach
waiting to happen, and it cannot be reconstructed after the fact.

Untrusted input
---------------
These files come from the open internet and end up embedded in a web page. SVG
is not a passive format — it carries script, event handlers, external
references and foreign objects. Everything fetched here is sanitised before it
is written, so a file on disk is already safe. See `sanitise_svg`.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "SourcingError", "LicenceRejected", "SourcedArt",
    "ALLOWED_LICENCES", "REJECTED_PATTERNS", "ATTRIBUTION_FILE",
    "sanitise_svg", "licence_ok", "search_commons", "fetch_art",
    "BRAND_PATTERNS", "looks_like_a_brand",
]

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ATTRIBUTION_FILE = "ATTRIBUTION.md"

#: Contact in the UA is Wikimedia's stated policy for automated access.
_UA = "rive-agentic-studio/1.0 (https://github.com/hesham88; hesham1988@gmail.com)"

#: Licences compatible with an MIT project. Public domain needs no attribution
#: but gets it anyway — crediting an artist costs one table row.
#: Matched as substrings, so each entry must be specific enough that it cannot
#: match something unrelated. A bare "pd" would match any licence containing
#: those two letters; "pdm" and "pd-" are the actual Commons templates.
ALLOWED_LICENCES = (
    "cc0", "public domain", "pdm", "pd-", "pd old", "no restrictions",
    "cc by 1.0", "cc by 2.0", "cc by 2.5", "cc by 3.0", "cc by 4.0",
)

#: Substrings that disqualify a licence outright, checked BEFORE the allowlist
#: so that "CC BY-SA 4.0" cannot match on its "cc by" prefix.
REJECTED_PATTERNS = (
    "-sa", " sa", "share", "-nc", " nc", "noncommercial", "non-commercial",
    "-nd", " nd", "noderiv", "fair use", "gfdl",
)


#: Title fragments that mark a file as a brand asset rather than a drawing.
#: A permissive licence on a file DEPICTING a trademark grants no trademark
#: rights, and the two are entirely separate permissions. Keyword search does
#: not know that: "fox" returns Fox Broadcasting, "dolphin" returns the Dolphin
#: emulator, "jellyfish" returns Jellyfish Media. Seven of the first
#: twenty-five files fetched were corporate logos.
BRAND_PATTERNS = (
    "logo", "wordmark", "brand", "emblem", "trademark",
    " inc", "corporation", "company", "channel", "media", "network",
)


def looks_like_a_brand(title: str) -> bool:
    """True when a title suggests a trademark rather than an illustration."""
    low = f" {title.lower()} "
    return any(pat in low for pat in BRAND_PATTERNS)


class SourcingError(RuntimeError):
    pass


class LicenceRejected(SourcingError):
    """Raised rather than returned.

    A refused licence must not be a value a caller can forget to check.
    """


# --- security -------------------------------------------------------------

_SCRIPT = re.compile(r"<script\b.*?</script\s*>", re.I | re.S)
_STYLE_IMPORT = re.compile(r"@import[^;]*;", re.I)
_FOREIGN = re.compile(r"<foreignObject\b.*?</foreignObject\s*>", re.I | re.S)
_DTD = re.compile(r"<!DOCTYPE[^>]*>|<!ENTITY[^>]*>", re.I)
_ON_ATTR = re.compile(r"""\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.I)
_JS_URL = re.compile(r"""("|')\s*javascript:[^"']*\1""", re.I)
_HREF_EXTERNAL = re.compile(
    r"""\s(?:xlink:)?href\s*=\s*("|')\s*(?!#)([a-z]+:|//)[^"']*\1""", re.I)
_USE_EXTERNAL = re.compile(
    r"""<use\b[^>]*\s(?:xlink:)?href\s*=\s*["']\s*[a-z]+:""", re.I)


def sanitise_svg(svg: str) -> tuple[str, list[str]]:
    """Strip everything executable or externally-referencing from an SVG.

    Returns the cleaned markup and a list of what was removed, because a silent
    sanitiser gives no way to notice that a source has started serving hostile
    files.

    This is allow-by-default markup with a denylist of known-dangerous
    constructs, which is weaker than parsing to a whitelist of shape elements.
    That is the right level here because the output is re-parsed by
    `parse_svg_document`, which reads only path geometry and fill colours, so
    anything surviving is discarded at that stage regardless. The sanitiser
    exists so the intermediate file on disk is not itself a hazard.
    """
    removed: list[str] = []

    def drop(pattern: re.Pattern[str], label: str, text: str) -> str:
        out, n = pattern.subn("", text)
        if n:
            removed.append(f"{label} x{n}")
        return out

    svg = drop(_DTD, "doctype/entity", svg)
    svg = drop(_SCRIPT, "<script>", svg)
    svg = drop(_FOREIGN, "<foreignObject>", svg)
    svg = drop(_STYLE_IMPORT, "@import", svg)
    svg = drop(_ON_ATTR, "event handler", svg)
    svg = drop(_JS_URL, "javascript: url", svg)
    svg = drop(_HREF_EXTERNAL, "external href", svg)
    if _USE_EXTERNAL.search(svg):
        removed.append("external <use>")
        svg = _USE_EXTERNAL.sub("<use ", svg)
    return svg, removed


# --- licensing ------------------------------------------------------------

def licence_ok(licence: str) -> bool:
    """True only for licences compatible with an MIT project.

    Unknown licences are refused. Defaulting to permitted would mean a source
    that stopped reporting metadata silently started producing unlicensed files.
    """
    if not licence:
        return False
    low = licence.strip().lower()
    if any(bad in low for bad in REJECTED_PATTERNS):
        return False
    return any(ok in low for ok in ALLOWED_LICENCES)


@dataclass
class SourcedArt:
    """One licensed SVG, with the provenance that makes it legal to use."""

    title: str
    svg: str
    licence: str
    artist: str
    source_url: str
    file_url: str
    sanitised: list[str] = field(default_factory=list)

    @property
    def kb(self) -> float:
        return len(self.svg.encode("utf-8")) / 1024

    def save(self, directory: str | Path) -> Path:
        """Write the SVG and its attribution row. Both, always."""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")[:60] or "art"
        path = d / f"{slug}.svg"
        path.write_text(self.svg, encoding="utf-8")

        record = d / ATTRIBUTION_FILE
        if not record.exists():
            record.write_text(
                "# Attribution\n\nVector art sourced from open repositories. "
                "Every file below is licensed for reuse and modification; credit "
                "is required wherever these appear.\n\n"
                "| File | Title | Artist | Licence | Source |\n"
                "| --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
        row = (f"| `{path.name}` | {self.title} | {self.artist or '-'} | "
               f"{self.licence} | {self.source_url} |\n")
        existing = record.read_text(encoding="utf-8")
        if row not in existing:
            record.write_text(existing + row, encoding="utf-8")
        return path


# --- fetching -------------------------------------------------------------

def _get(url: str, *, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SourcingError(f"{url} -> HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise SourcingError(f"{url} -> {e.reason}") from e
    except (TimeoutError, OSError) as e:
        # A socket read that stalls raises TimeoutError, which is NOT a
        # URLError — so without this it escapes as an unhandled exception and
        # one slow file aborts an entire harvest. Batch fetching from public
        # galleries hits this regularly.
        raise SourcingError(f"{url} -> {type(e).__name__}: {e}") from e


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def search_commons(subject: str, *, limit: int = 10,
                   max_bytes: int = 2_000_000) -> list[dict]:
    """Search Wikimedia Commons for SVGs, returning candidates with licences.

    Candidates come back unfetched and NOT filtered by licence, each carrying an
    `allowed` flag. A caller can then see what was rejected and why, rather than
    receiving a mysteriously short list.

    `max_bytes` flags the enormous files Commons is full of — a 4 MB SVG is
    almost always a detailed map rather than a usable illustration.
    """
    query = urllib.parse.quote(f"{subject} filemime:image/svg+xml")
    url = (f"{COMMONS_API}?action=query&format=json&generator=search"
           f"&gsrsearch={query}&gsrnamespace=6&gsrlimit={int(limit)}"
           f"&prop=imageinfo&iiprop=url|extmetadata|size")
    try:
        data = json.loads(_get(url))
    except json.JSONDecodeError as e:
        raise SourcingError(f"Commons returned non-JSON for {subject!r}") from e

    out: list[dict] = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        size = int(info.get("size") or 0)
        licence = _strip_tags((meta.get("LicenseShortName") or {}).get("value", ""))
        out.append({
            "title": re.sub(r"^File:|\.svg$", "", page.get("title", ""), flags=re.I),
            "file_url": (info.get("url") or "").split("?")[0],
            "source_url": info.get("descriptionurl", ""),
            "licence": licence,
            "artist": _strip_tags((meta.get("Artist") or {}).get("value", ""))[:80],
            "bytes": size,
            "brand": looks_like_a_brand(page.get("title", "")),
            "allowed": licence_ok(licence) and not looks_like_a_brand(page.get("title", "")),
            "too_big": size > max_bytes,
        })
    return sorted(out, key=lambda c: (not c["allowed"], c["too_big"], c["bytes"]))


def fetch_art(candidate: dict, *, max_bytes: int = 2_000_000) -> SourcedArt:
    """Download, licence-check and sanitise one candidate."""
    licence = candidate.get("licence", "")
    if not licence_ok(licence):
        raise LicenceRejected(
            f"{candidate.get('title', '?')!r} is {licence or 'unlicensed'} - "
            f"not usable in an MIT project"
        )
    size = int(candidate.get("bytes") or 0)
    if size > max_bytes:
        raise SourcingError(
            f"{candidate.get('title', '?')!r} is {size:,} B, over the "
            f"{max_bytes:,} B cap - probably a map rather than an illustration"
        )

    raw = _get(candidate["file_url"])
    text = raw.decode("utf-8", "replace")
    if "<svg" not in text[:4000].lower():
        raise SourcingError(f"{candidate['file_url']} did not return SVG markup")

    clean, removed = sanitise_svg(text)
    return SourcedArt(
        title=candidate.get("title", "art"), svg=clean, licence=licence,
        artist=candidate.get("artist", ""), source_url=candidate.get("source_url", ""),
        file_url=candidate["file_url"], sanitised=removed,
    )
