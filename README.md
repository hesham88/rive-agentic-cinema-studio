# Rive Agentic Interactive Cinema and Web Studio

Turn a sentence into an interactive, animated Rive asset — researched,
generated, vectorised, rigged, animated, scored, and exported as a `.riv` the
web can run.

**Live:** https://rive-agentic-studio.web.app

## What it does

A prompt goes in. The pipeline researches how the subject is really drawn
(Parallel Search), generates the art (Gemini), traces it to vector, simplifies
the tracer's noise away, then drives the Rive editor over MCP to build shapes,
rig them, keyframe them, bind a view model and export a runtime file.

One measured run, prompt to shipped asset:

| step | | |
| --- | --- | --- |
| brief | 1 | sentence |
| research | 10 | sources |
| render | 86 KB | raster |
| trace | 252 | path commands |
| simplify | 41 | path commands |
| ship | 868 | bytes |

A hundredth the size of the raster it came from, infinitely scalable, and
animatable.

## The interface is Rive too

The studio's own controls are not CSS. The button, switch, sliders, text field,
select, tab bar, progress bar and panel are eight artboards in a single 5.3 KB
`ui-kit.riv`, drawn by Rive and animated by the engine's spring maths — the same
frame-rate-independent law that drives the camera engine.

Each control wraps a real focusable element (`<button>`, `<input type="range">`,
a native `<select>`) sitting invisibly underneath, carrying focus, keyboard
operation, screen-reader semantics and IME. The canvas is `aria-hidden` and
takes no pointer events. A screen reader hears a button; a mouse sees Rive.

## Layout

```
packages/rive-engine    the library
  src/core              pure, imports NOTHING — no React, no Rive, no Node
  src/react             hooks, and the Rive-rendered UI kit
apps/studio             Next.js app, static export
tools/genassets         Python generative pipeline + Rive MCP client
```

`packages/rive-engine` is consumable on its own. `core` has no dependencies at
all, so the inspection, camera and motion maths can be used anywhere.

## Running it

```bash
npm install
npm run dev            # studio at localhost:3000
npx vitest run         # unit tests
npm run test:e2e       # Playwright (workers: 1 — WASM/WebGL contention)
npm run deploy         # pinned to the rive-agentic-studio project
```

The Python pipeline needs the Rive desktop app running with a file open; it
talks to the editor's MCP server on `127.0.0.1:9791`.

```bash
cd tools/genassets && python -m pytest
```

## Notes for anyone building on Rive

Three things cost real debugging time and are not in the docs:

- **`autoBind` defaults to `false`.** Without it `rive.viewModelInstance` is
  `null`, so a fully data-bound file reports zero properties and looks inert.
- **Rive has two input systems that do not overlap.** Classic state-machine
  inputs and view-model properties are separate worlds; a data-bound file
  enumerates zero state-machine inputs while being fully interactive.
- **Scale is a percentage.** A keyframe of `1.0` means 1%, not 100%.

## License

MIT — see [LICENSE](LICENSE).
