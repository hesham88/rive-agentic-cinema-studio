"""Find licensed vector art with Parallel, across the whole open web.

Why this is not `sourcing.search_commons`
-----------------------------------------
`sourcing.py` queries one API — Wikimedia Commons — with a keyword. That is a
fine fetcher and a poor finder. Commons is an encyclopedia's media library, so a
keyword search for a creature returns diagrams, range maps, heraldry and
corporate logos long before it returns an illustration anyone would animate.
Twenty subjects yielded eighteen usable files, and seven of the first
twenty-five were trademarks.

The open web has far better: openclipart, SVG Repo, publicdomainvectors,
freesvg, reshot, and the public-domain scans on Internet Archive and NYPL. What
it does not have is one API across them. That is exactly the shape of problem
Parallel solves — Search finds the pages, Extract reads them even when they are
client-rendered, and Task returns a cited, structured answer.

So discovery and fetching are separated. This module finds candidate URLs and
judges what is there; `sourcing.py` still owns the licence gate, the sanitiser
and the attribution record, because those must apply to every file regardless of
how it was found.

The licence question is asked, not assumed
------------------------------------------
A search result saying "free SVG" means nothing legally. Parallel is asked for
the licence AS A FIELD, with citations, so the answer is traceable to a page
rather than inferred from a site's marketing copy. Anything that comes back
unclear is reported as unclear and skipped — an unlicensed asset in a public
repo is a problem no amount of convenience is worth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .parallel import ParallelClient

__all__ = [
    "SOURCE_SITES", "ART_SOURCE_SCHEMA", "Candidate",
    "DIRECT_URL_PATTERNS", "direct_svg_url",
    "discover", "svg_urls_in", "harvest",
    "openclipart_ids", "openclipart_candidates",
]

#: Sites that publish genuinely reusable vector art. Naming them in the query
#: keeps Parallel from returning stock-photo storefronts, whose "free" means a
#: watermarked preview and a licence that forbids derivatives.
SOURCE_SITES = (
    # Listed in the order they have proved useful. Openclipart is first because
    # every file there is CC0 — no licence ambiguity to resolve — and because it
    # serves genuine illustrations rather than icons: the first fetch came back
    # at 978 paths, which is a drawing, not a pictogram.
    "openclipart.org",
    "svgrepo.com",
    "publicdomainvectors.org",
    "commons.wikimedia.org",
)

#: Fields chosen so the answer carries facts rather than prose. A field named
#: `licence` returns a licence; a field named `description` returns an essay.
ART_SOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "description": "Individual artworks found, most usable first",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "page_url": {"type": "string", "description": "Page the artwork is on"},
                    "svg_url": {"type": "string", "description": "Direct .svg file URL if stated on the page, else empty"},
                    "licence": {"type": "string", "description": "Exact licence name, e.g. CC0 1.0, Public Domain, CC BY 4.0. Say UNCLEAR if the page does not state one."},
                    "author": {"type": "string"},
                    "is_illustration": {"type": "boolean", "description": "True for a drawing of the subject; false for a logo, trademark, diagram, map or chart"},
                    "style": {"type": "string", "description": "flat / line-art / detailed / silhouette / cartoon"},
                },
            },
        },
    },
}

_SVG_HREF = re.compile(r'https?://[^\s"\'<>)]+\.svg', re.I)


@dataclass
class Candidate:
    """One artwork Parallel found, before anything is downloaded."""

    title: str
    page_url: str
    svg_url: str
    licence: str
    author: str = ""
    style: str = ""
    is_illustration: bool = True
    #: Where the finding came from, so a bad result is traceable.
    basis: list[str] = field(default_factory=list)

    @property
    def licence_stated(self) -> bool:
        return bool(self.licence) and self.licence.strip().upper() != "UNCLEAR"

    def as_sourcing_dict(self) -> dict:
        """Shape `sourcing.fetch_art` accepts, so the licence gate, the
        sanitiser and the attribution record all still apply."""
        return {
            "title": self.title,
            "file_url": self.svg_url,
            "source_url": self.page_url,
            "licence": self.licence,
            "artist": self.author,
            "bytes": 0,
        }


#: Direct-download URL patterns, keyed by host.
#:
#: Discovery returns the PAGE an artwork lives on. Asking a language model for
#: the direct file URL as well does not work — it produced
#: `publicdomainvectors.org/download.php?file=tortluga.svg`, which 404s, because
#: a plausible-looking URL is not a real one and nothing in the pipeline was
#: checking.
#:
#: These galleries all expose a deterministic download path derived from the
#: page path, so the URL can be constructed rather than guessed or scraped.
#: Constructed URLs are still fetched and checked for a real SVG body, so a site
#: changing its scheme shows up as a failed fetch rather than a corrupt file.
DIRECT_URL_PATTERNS: dict[str, "Callable[[re.Match[str]], str]"] = {}


def _register(host: str, page_re: str, template: str) -> None:
    DIRECT_URL_PATTERNS[host] = (re.compile(page_re, re.I), template)


# svgrepo.com/svg/60026/swimming-turtle -> /download/60026/swimming-turtle.svg
_register("svgrepo.com", r"/svg/(\d+)/([\w-]+)",
          "https://www.svgrepo.com/download/{0}/{1}.svg")
# openclipart.org/detail/184460/baby-sea-turtle -> /download/184460/
_register("openclipart.org", r"/detail/(\d+)",
          "https://openclipart.org/download/{0}/")
# freesvg.org has no derivable pattern: the file name is not the page slug, so
# /img/<slug>.svg 404s. Left out deliberately — a pattern that produces a wrong
# URL is worse than none, because the fetch failure looks like a dead site
# rather than a bad guess. Such pages fall through to the extract step.


def direct_svg_url(page_url: str) -> str:
    """Build the direct `.svg` URL for a gallery page, or return empty.

    Empty means "this host has no known pattern", which is a signal to read the
    page rather than a failure.
    """
    if not page_url:
        return ""
    for host, (page_re, template) in DIRECT_URL_PATTERNS.items():
        if host not in page_url:
            continue
        path = urllib.parse.urlsplit(page_url).path
        m = page_re.search(path)
        if m:
            return template.format(*m.groups())
    return ""


def svg_urls_in(markdown: str) -> list[str]:
    """Direct `.svg` links in an extracted page, de-duplicated in order."""
    return list(dict.fromkeys(_SVG_HREF.findall(markdown or "")))


def discover(subject: str, *, client: ParallelClient | None = None,
             processor: str = "core", max_wait: float = 900.0) -> list[Candidate]:
    """Ask Parallel for licensed vector art of one subject.

    `core` rather than `lite`: a lite run on this question came back with
    conference listings and robotics papers. The tier is the difference between
    a search engine and an answer.
    """
    c = client or ParallelClient()
    sites = " OR ".join(f"site:{s}" for s in SOURCE_SITES)
    objective = (
        f"Find downloadable SVG vector illustrations of a {subject} that are "
        f"free to reuse AND to modify. Prefer {sites}. "
        f"For each result give the exact licence as stated on its page — if the "
        f"page does not state one, answer UNCLEAR rather than guessing. "
        f"Exclude company logos, trademarks, brand marks, scientific diagrams, "
        f"range maps and charts: this is for character animation, so only "
        f"drawings of the subject itself count."
    )
    report = c.research(objective, ART_SOURCE_SCHEMA, processor=processor, max_wait=max_wait)
    content = report.content if isinstance(report.content, dict) else {}
    out: list[Candidate] = []
    for row in content.get("results") or []:
        if not isinstance(row, dict):
            continue
        out.append(Candidate(
            title=(row.get("title") or "").strip(),
            page_url=(row.get("page_url") or "").strip(),
            svg_url=(row.get("svg_url") or "").strip(),
            licence=(row.get("licence") or "").strip(),
            author=(row.get("author") or "").strip(),
            style=(row.get("style") or "").strip(),
            is_illustration=bool(row.get("is_illustration", True)),
            basis=report.cited("results"),
        ))
    return out


def harvest(candidates: list[Candidate], *, client: ParallelClient | None = None,
            limit: int = 12) -> list[Candidate]:
    """Fill in missing `svg_url`s by reading the pages.

    Most galleries put the download link behind JavaScript, so a plain fetch
    returns an empty shell. Extract renders the page, which is the whole reason
    it is worth a call.
    """
    # Construct from the page URL first — deterministic, free, and correct more
    # often than either the model's guess or a scrape. Anything the model
    # supplied is discarded when a pattern exists, because the pattern is
    # derived from the site's own scheme and the guess is not.
    for cand in candidates:
        built = direct_svg_url(cand.page_url)
        if built:
            cand.svg_url = built

    need = [c for c in candidates
            if c.is_illustration and c.licence_stated and not c.svg_url and c.page_url]
    if not need:
        return candidates
    c = client or ParallelClient()
    pages = c.extract([x.page_url for x in need[:limit]])
    by_url = {p.url: p for p in pages if getattr(p, "url", None)}
    for cand in need[:limit]:
        page = by_url.get(cand.page_url)
        if not page:
            continue
        urls = svg_urls_in(getattr(page, "excerpts", None) and "\n".join(page.excerpts)
                           or getattr(page, "content", "") or "")
        if urls:
            cand.svg_url = urls[0]
    return candidates


# --- openclipart bulk ------------------------------------------------------

OPENCLIPART_SEARCH = "https://openclipart.org/search/?query={}"
_DETAIL_ID = re.compile(r"/detail/(\d+)/([\w-]*)")


def openclipart_ids(subject: str, *, timeout: int = 40) -> list[tuple[str, str]]:
    """Search openclipart directly and return (id, slug) pairs.

    Parallel is the right tool for finding art ACROSS the open web and for
    resolving a licence that a page states only in prose. It is the wrong tool
    for bulk-listing one site that answers a plain HTML search with thirty-two
    results, because that costs a research run per subject to rediscover what a
    single GET already returns.

    So this exists alongside `discover`, not instead of it. Openclipart is
    uniformly CC0, which removes the licence question that Parallel is otherwise
    needed to answer.

    The documented JSON API is not used: it now answers with HTML, so the
    HTML is what gets parsed.
    """
    url = OPENCLIPART_SEARCH.format(urllib.parse.quote(subject))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; rive-agentic-studio/1.0)",
        "Accept": "text/html",
    })
    try:
        html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return []
    seen: dict[str, str] = {}
    for cid, slug in _DETAIL_ID.findall(html):
        seen.setdefault(cid, slug)
    return list(seen.items())


def openclipart_candidates(subject: str, *, limit: int = 8) -> list[Candidate]:
    """Openclipart results as `Candidate`s, ready for the licence gate.

    Everything on openclipart is CC0, which is stated site-wide rather than
    per-page. That is asserted here rather than parsed, and it is the one place
    in this module where a licence is not read from the artwork's own page — so
    it is worth being explicit that it rests on the site's blanket terms.
    """
    out: list[Candidate] = []
    for cid, slug in openclipart_ids(subject)[:limit]:
        out.append(Candidate(
            title=(slug or f"openclipart-{cid}").replace("-", " ").strip().title(),
            page_url=f"https://openclipart.org/detail/{cid}/{slug}",
            svg_url=f"https://openclipart.org/download/{cid}/",
            licence="CC0 1.0",
            author="", style="", is_illustration=True,
            basis=["https://openclipart.org/ — all uploads are released CC0"],
        ))
    return out
