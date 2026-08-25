"""Harvest the full design record for a refero style, tokens included.

What the local corpus was missing
---------------------------------
`_OPERATIONS/study/design-library/refero.jsonl` holds 1,290 systems as
structured JSON, and it is genuinely useful — but it carries only the fields the
original scrape asked for. The live page carries more: a complete `DESIGN.md`,
a **Tailwind v4** `@theme` block, and a **CSS custom properties** block with
every colour, radius, spacing step and font already named as a variable.

Those are the parts an implementer actually needs. A north star tells you what
room the interface is in; `--color-iris-glow: #6199f6` tells you what to type.

How the page yields them
------------------------
The tabs (Preview / DESIGN.md / Tailwind v4 / CSS Variables / Design Tokens)
look like they need clicking, and a first attempt reached for a JS-aware
fetcher on that assumption. They do not: the page ships every tab's content
inline in one ~270 KB document, so a plain GET returns all of it and the tabs
only decide what is displayed. Worth knowing before spending a render on it.

`/tailwind` and `/tokens` as URL suffixes both 404 — there is no per-tab
endpoint to fetch.

Provenance
----------
Refero's records are themselves derived from a screenshot and marked as such in
places ("detected in extracted data but not described by AI"). Treat a token as
a strong observation about a shipped page rather than as the team's own
published system, and prefer the CSS block over the prose when they disagree.
"""

from __future__ import annotations

import html as _html
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["StyleRecord", "fetch_style", "parse_style", "css_vars", "tailwind_theme"]

_UA = "Mozilla/5.0 (compatible; rive-agentic-studio/1.0; +https://github.com/hesham88)"

_CSS_BLOCK = re.compile(r"```css\s*(.*?)```", re.S)
_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
_THEME = re.compile(r"@theme\s*\{(.*?)\n\}", re.S)
_TABLE_ROW = re.compile(r"\|\s*([^|]+?)\s*\|\s*`(#[0-9a-fA-F]{3,8})`\s*\|\s*`(--[\w-]+)`\s*\|\s*([^|]*)\|")


@dataclass
class StyleRecord:
    """One refero style, as much of it as the page carries."""

    url: str
    name: str = ""
    north_star: str = ""
    #: `--name` -> value, from the CSS custom-properties block.
    variables: dict[str, str] = field(default_factory=dict)
    #: The Tailwind v4 `@theme` body verbatim, if present.
    theme_block: str = ""
    #: (human name, hex, css var, role) from the colour table.
    colours: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: The whole DESIGN.md-ish body, for anything not parsed out.
    markdown: str = ""

    @property
    def accent(self) -> str:
        """The one chromatic colour, by the role text rather than by guessing.

        Every strong system in the corpus reserves a single accent, and its role
        says so — "sole chromatic accent", "the only warm accent". Reading the
        role beats picking the most saturated hex, which would return whichever
        decorative tint happened to be brightest.
        """
        for _, hex_, _, role in self.colours:
            low = role.lower()
            if "sole chromatic" in low or "only chromatic" in low or "sole warm" in low:
                return hex_
        return ""

    def var(self, name: str, default: str = "") -> str:
        return self.variables.get(name if name.startswith("--") else f"--{name}", default)


def _get(url: str, *, timeout: int = 40) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def css_vars(text: str) -> dict[str, str]:
    """Every `--name: value` in the page's CSS blocks.

    Scoped to fenced ```css blocks rather than run over the whole document, so
    a variable named in prose is not mistaken for a declaration.
    """
    out: dict[str, str] = {}
    for block in _CSS_BLOCK.findall(text):
        for name, value in _VAR.findall(block):
            out[name] = value.strip()
    return out


def tailwind_theme(text: str) -> str:
    """The Tailwind v4 `@theme { ... }` body, verbatim."""
    m = _THEME.search(text)
    return m.group(1).strip() if m else ""


def parse_style(html: str, url: str = "") -> StyleRecord:
    """Pull the record out of a fetched page."""
    # The page is server-rendered markdown inside HTML; stripping tags leaves
    # the document intact, which is all the parsing this needs.
    text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "", text)
    # The document is markdown that was HTML-escaped on the way in, so a font
    # stack arrives as `&#x27;Inter&#x27;` and a dash as `&#8212;`. Unescaping
    # after tag-stripping is what turns the variables into usable values —
    # without it every --font-* token is the literal string "&#x27".
    text = _html.unescape(text)

    # The breadcrumb is the reliable anchor: "/ Styles / <Name>". Stripping
    # tags removes the H1's markup, so a "^# " pattern finds nothing.
    name = ""
    if m := re.search(r"/\s*Styles\s*/\s*([^\n/]{1,60})", text):
        name = m.group(1).strip()

    # The north star is the first real paragraph after the LAST mention of the
    # name — earlier mentions are the breadcrumb and the screenshot's alt text.
    north = ""
    if name:
        for line in (ln.strip() for ln in text.rsplit(name, 1)[-1].split("\n")):
            if len(line) > 30 and not line.startswith(("|", "#", "`", "[", "-")):
                north = " ".join(line.split())[:400]
                break

    return StyleRecord(
        url=url,
        name=name,
        north_star=north,
        variables=css_vars(text),
        theme_block=tailwind_theme(text),
        colours=[(a.strip(), b, c, d.strip()) for a, b, c, d in _TABLE_ROW.findall(text)],
        markdown=text,
    )


def fetch_style(url_or_id: str, *, timeout: int = 40) -> StyleRecord:
    """Fetch and parse one style page.

    Accepts a full URL or a bare style id.
    """
    url = url_or_id
    if not url.startswith("http"):
        url = f"https://styles.refero.design/style/{url_or_id}"
    try:
        return parse_style(_get(url, timeout=timeout), url)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url} -> HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"{url} -> {type(e).__name__}: {e}") from e
