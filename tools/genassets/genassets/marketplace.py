"""Fetch files from the Rive Marketplace.

What is and is not possible
---------------------------
A marketplace page embeds the direct runtime URL of its own file, at a stable
pattern:

    https://rive.app/community/files/{slug}/
    -> https://public.rive.app/community/runtime-files/{slug}.riv

The second URL can also be built from the slug alone without fetching the page,
which makes bulk fetching one request per file instead of two. The page is still
worth reading when the title, author or licence is wanted.

**Fetching is not remixing.** A `.riv` is compiled output — one-way by design —
so a downloaded file can be inspected, played and driven at runtime, but not
reopened in the editor. Editing means the Marketplace *Remix* button, which
copies the file into your own account, and everything there is CC BY. See
`_OPERATIONS/study/06-round-trip.md`.

So this module is deliberately named for what it does: fetch and inspect. It
does not pretend to clone.

Licence
-------
Every Marketplace file is CC BY. Attribution is not optional, so `FetchedFile`
carries the source URL and the module writes an attribution record beside any
file it saves. A fetched asset that loses its provenance is a licence breach
waiting to happen.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "MarketplaceError",
    "FetchedFile",
    "slug_from_url",
    "runtime_url",
    "fetch_file",
    "fetch_many",
    "ATTRIBUTION_FILE",
]

PAGE_BASE = "https://rive.app/community/files"
RUNTIME_BASE = "https://public.rive.app/community/runtime-files"

#: Written beside downloaded files. CC BY requires attribution, and a directory
#: of anonymous `.riv`s cannot satisfy it.
ATTRIBUTION_FILE = "ATTRIBUTION.md"

_SLUG = re.compile(r"(\d+-\d+-[a-z0-9-]+)")
_RIV_IN_PAGE = re.compile(
    r"https://public\.rive\.app/community/runtime-files/([0-9a-z-]+)\.riv"
)
_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)


class MarketplaceError(RuntimeError):
    pass


@dataclass
class FetchedFile:
    """A `.riv` downloaded from the Marketplace, with its provenance."""

    slug: str
    bytes: bytes
    page_url: str
    runtime_url: str
    title: str = ""
    #: Other files the page referenced — a marketplace page lists related work.
    related: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.bytes)

    @property
    def is_rive(self) -> bool:
        """Rive files start with the ASCII fingerprint `RIVE`."""
        return self.bytes[:4] == b"RIVE"

    def save(self, directory: str | Path) -> Path:
        """Write the file and append its attribution.

        Both, always. Saving the bytes without the credit is the failure mode
        this module exists to prevent.
        """
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{self.slug}.riv"
        path.write_bytes(self.bytes)

        record = d / ATTRIBUTION_FILE
        header = (
            "# Attribution\n\n"
            "Files fetched from the Rive Marketplace, which licenses all "
            "community files under CC BY. Credit is required wherever these "
            "are used.\n\n"
            "| File | Title | Source |\n| --- | --- | --- |\n"
        )
        if not record.exists():
            record.write_text(header, encoding="utf-8")
        line = f"| `{self.slug}.riv` | {self.title or '—'} | {self.page_url} |\n"
        existing = record.read_text(encoding="utf-8")
        if line not in existing:
            record.write_text(existing + line, encoding="utf-8")
        return path


def slug_from_url(url: str) -> str:
    """Extract `1714-4322-rives-animated-emojis` from any marketplace URL form."""
    m = _SLUG.search(url)
    if not m:
        raise MarketplaceError(
            f"no marketplace slug in {url!r} — expected something like "
            f"'1714-4322-rives-animated-emojis'"
        )
    return m.group(1)


def runtime_url(slug_or_url: str) -> str:
    """The direct `.riv` URL for a slug or a page URL."""
    return f"{RUNTIME_BASE}/{slug_from_url(slug_or_url)}.riv"


def _get(url: str, *, timeout: int = 45) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            # Without a browser-shaped UA the CDN answers some requests with an
            # HTML error page, which would then be saved as a corrupt `.riv`.
            "User-Agent": "Mozilla/5.0 (compatible; rive-agentic-studio/1.0)",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise MarketplaceError(f"{url} -> HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise MarketplaceError(f"{url} -> {e.reason}") from e


def fetch_file(
    slug_or_url: str,
    *,
    read_page: bool = True,
    timeout: int = 45,
) -> FetchedFile:
    """Download one Marketplace file.

    `read_page=False` skips the HTML entirely and fetches the runtime URL
    directly — one request instead of two, at the cost of the title and the
    related links. Worth it when fetching in bulk.
    """
    slug = slug_from_url(slug_or_url)
    page_url = f"{PAGE_BASE}/{slug}/"
    title, related = "", []

    if read_page:
        try:
            html = _get(page_url, timeout=timeout).decode("utf-8", "replace")
            if m := _TITLE.search(html):
                # The page is client-rendered, so <title> is the app shell's
                # generic one. Fall back to the slug, which carries the real
                # name after its two id segments.
                raw = m.group(1).strip()
                title = raw if raw.lower() not in ("rive", "rive - marketplace") else ""
            if not title:
                title = slug.split("-", 2)[-1].replace("-", " ").title()
            found = _RIV_IN_PAGE.findall(html)
            related = [s for s in dict.fromkeys(found) if s != slug]
        except MarketplaceError:
            # A missing page is not a reason to skip the file: the runtime URL
            # is derivable from the slug and is the thing actually wanted.
            pass

    url = runtime_url(slug)
    data = _get(url, timeout=timeout)
    fetched = FetchedFile(
        slug=slug, bytes=data, page_url=page_url, runtime_url=url,
        title=title, related=related,
    )
    if not fetched.is_rive:
        raise MarketplaceError(
            f"{url} returned {len(data)} bytes that are not a Rive file "
            f"(starts with {data[:8]!r}) — the slug is probably wrong"
        )
    return fetched


def fetch_many(
    slugs: list[str],
    directory: str | Path,
    *,
    read_page: bool = True,
    verbose: bool = True,
) -> list[FetchedFile]:
    """Fetch several files, saving each with its attribution.

    One failure does not stop the rest — a bad slug in a list of twenty should
    cost one file, not the batch.
    """
    out: list[FetchedFile] = []
    for s in slugs:
        try:
            f = fetch_file(s, read_page=read_page)
            f.save(directory)
            out.append(f)
            if verbose:
                print(f"  {f.slug}  {f.size:,} B  {f.title[:48]}", flush=True)
        except MarketplaceError as e:
            if verbose:
                print(f"  FAILED {s}: {e}", flush=True)
    return out
