"""Parsing a refero style page into usable tokens.

The point of this module is the part the local corpus lacks: the Tailwind v4
`@theme` block and the CSS custom properties. A north star says what room the
interface is in; `--color-iris-glow: #6199f6` says what to type.

No network here. Live fetching is exercised by hand; a unit test that depended
on refero's current markup would fail for reasons unrelated to this code.
"""

from __future__ import annotations

from genassets.refero import css_vars, parse_style, tailwind_theme

PAGE = """
<html><body>
<nav>[](https://refero.design) / Styles / Frame.io</nav>
<h1>Frame.io</h1>
<p>Midnight cinema projection room.</p>
| Name | Hex | Variable | Role |
|---|---|---|---|
| Carbon Vellum | `#fcfcfc` | `--color-carbon-vellum` | Primary text on dark |
| Iris Glow | `#6199f6` | `--color-iris-glow` | Sole chromatic accent - icons and links |
| Smoke | `#757580` | `--color-smoke` | Secondary body text |

### CSS Custom Properties

```css
:root {
  /* Colors */
  --color-carbon-vellum: #fcfcfc;
  --color-iris-glow: #6199f6;
  --text-display: 80px;
  --leading-display: 0.96;
  --tracking-display: -3.6px;
  --radius-pills: 100px;
  --font-framegothic: &#x27;FrameGothic&#x27;, ui-sans-serif;
}
```

```css
@theme {
  --color-obsidian: #0a0a13;
  --spacing-unit: 8px;
}
```
</body></html>
"""


def test_css_variables_are_extracted() -> None:
    r = parse_style(PAGE)
    assert r.variables["--color-iris-glow"] == "#6199f6"
    assert r.variables["--text-display"] == "80px"
    assert r.variables["--tracking-display"] == "-3.6px"
    assert r.variables["--radius-pills"] == "100px"


def test_html_entities_are_decoded() -> None:
    """A font stack arrives escaped; without unescaping every --font-* token
    is the literal string "&#x27"."""
    r = parse_style(PAGE)
    assert r.variables["--font-framegothic"].startswith("'FrameGothic'")
    assert "&#x27" not in r.variables["--font-framegothic"]


def test_the_tailwind_theme_block_is_captured() -> None:
    r = parse_style(PAGE)
    assert "--color-obsidian: #0a0a13;" in r.theme_block
    assert "--spacing-unit: 8px;" in r.theme_block


def test_colour_table_rows_are_parsed() -> None:
    r = parse_style(PAGE)
    names = {c[0] for c in r.colours}
    assert {"Carbon Vellum", "Iris Glow", "Smoke"} <= names


def test_the_accent_is_found_by_ROLE_not_by_saturation() -> None:
    """Picking the most saturated hex would return whichever decorative tint
    happened to be brightest. The role text says which one is the accent."""
    r = parse_style(PAGE)
    assert r.accent == "#6199f6"


def test_name_comes_from_the_breadcrumb() -> None:
    """Tag-stripping removes the H1's markup, so a "^# " pattern finds nothing."""
    assert parse_style(PAGE).name == "Frame.io"


def test_variables_outside_css_blocks_are_ignored() -> None:
    """A variable named in prose is not a declaration."""
    assert css_vars("Set --color-fake: #fff; in your theme.") == {}


def test_missing_theme_block_is_empty_not_an_error() -> None:
    assert tailwind_theme("<p>no css here</p>") == ""


def test_var_accessor_tolerates_a_missing_prefix() -> None:
    r = parse_style(PAGE)
    assert r.var("color-iris-glow") == r.var("--color-iris-glow") == "#6199f6"
    assert r.var("--nope", "fallback") == "fallback"
