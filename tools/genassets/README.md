# genassets — generative asset pipeline

Authoring-time only. Turns a prompt or an uploaded image into a Rive-ready asset.
**Never** imported by the runtime app or its build (BIBLE §1).

## Modules

| Module | Job |
| --- | --- |
| `gemini.py` | One client for all four models, with a spend cap checked *before* each call |
| `normalize.py` | Decode by content, re-encode true PNG, optional quantize |
| `cutout.py` | Key-color → alpha, despill, edge-color detection, trim to content |
| `vectorize.py` | Classify the image, pick the tracer profile, enforce a path budget |
| `rivepath.py` | SVG path data → Rive command objects (pure, fully tested) |

## The findings this encodes

1. **Gemini returns JPEG whatever you name the file.** Extension-keyed tracers fail
   with a misleading "no image file found"; JPEG artifacts turned a 4-colour source
   into 46 traced colours. `normalize.py` sniffs magic bytes and re-encodes.
2. **One tracer profile cannot serve all art.** The profile that renders an icon
   perfectly destroys an illustration. `vectorize.py` classifies first.
3. **Photos must not be vectorized.** The only faithful photo trace needed 5154
   paths / 5 MB. `vectorize()` refuses them by default.
4. **Rive's `createShapes` does not take SVG `d` strings.** It needs structured
   `moveTo`/`lineTo`/`cubicTo`/`close` objects, and `#aarrggbb` colours with alpha
   FIRST. That translation is `rivepath.py`.
5. **Background removal should key a colour, not request transparency.** JPEG has no
   alpha, so "make it transparent" yields an arbitrary matte. `remove_background()`
   asks for flat magenta; `cutout.key_to_alpha()` removes it losslessly with despill.

## Two routes into Rive

- **`assets_tool.addSvgInstance`** — import an SVG asset as an editable shape
  hierarchy. Preferred: Rive does the parsing.
- **`path_editor.createShapes`** with `rivepath.parse_path()` output — for
  programmatic control over individual shapes.

## Tests

```bash
cd tools/genassets && python -m pytest tests/ -q   # 24 passing
```
