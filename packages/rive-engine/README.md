# rive-engine

Turns a `.riv` file into an inspectable, controllable React component.

Two entry points:

| Import | Contains | Dependencies |
| --- | --- | --- |
| `rive-engine` | Domain types + pure functions | **none** |
| `rive-engine/react` | Hooks + components | React, `@rive-app/react-webgl2` |

`rive-engine` (core) imports nothing — not React, not the Rive runtime, not Node
builtins. It is portable to any consumer: a Node script, a non-React app, or a
CSP-restricted artifact build.

## Quick start

```tsx
'use client';

import { useState } from 'react';
import {
  ErrorPanel,
  InputControls,
  ManifestTree,
  RiveStage,
  useRiveController,
  useRiveSource,
  type RiveSource,
  type Selection,
} from 'rive-engine/react';

export function Inspector() {
  const [source, setSource] = useState<RiveSource | null>(null);
  const [selected, setSelected] = useState<Selection | null>(null);

  const { riveFile, error: loadError } = useRiveSource(source);

  const { RiveComponent, manifest, inputs, error: contentError } = useRiveController({
    riveFile,
    artboard: selected?.artboard,
    stateMachine: selected?.stateMachine,
  });

  return (
    <>
      <ErrorPanel error={loadError ?? contentError} />
      <ManifestTree manifest={manifest} selected={selected} onSelect={setSelected} />
      <RiveStage component={RiveComponent} className="aspect-video w-full" />
      <InputControls inputs={inputs} />
    </>
  );
}
```

## The one rule that matters

**Call `useRiveController` exactly once per file.**

It owns the Rive instance, and that instance only loads when its `RiveComponent`
is actually rendered. Call the hook twice and you mount two instances; the one
whose component you never render stays unloaded forever, so its `manifest` and
`inputs` are permanently empty — with no error to tell you why.

Pass `RiveComponent` down to `RiveStage` (or render it yourself). Never call the
hook again to "get the component somewhere else".

## API

### `rive-engine` — core, dependency-free

- `inspectRiveContents(contents) => RiveManifest` — pure mapper from the runtime's
  `contents` structure to the domain manifest. Tolerates missing fields; retains
  unrecognized input type tags as `kind: 'unknown'` with `rawType` rather than
  dropping them.
- `classifyLoadError(err: unknown) => RiveLoadError` — maps any throwable to one of
  four kinds: `parse`, `wasm`, `network`, `empty`. Always preserves the original
  message.
- `handleKey(artboard, stateMachine, inputName) => string` — stable input identity.
- `RIVE_INPUT_TYPE` — the runtime's numeric tags (`Number: 56`, `Trigger: 58`,
  `Boolean: 59`).
- Types: `RiveManifest`, `ArtboardInfo`, `StateMachineInfo`, `InputInfo`,
  `RiveInputKind`, `RiveLoadError`, `RiveContentsLike`.

### `rive-engine/react`

- `useRiveSource(source)` → `{ riveFile, error, status }`. Accepts
  `{ kind: 'url', url }` or `{ kind: 'buffer', buffer }`. Loading only — it
  deliberately returns no manifest (see below).
- `useRiveController({ riveFile, artboard?, stateMachine?, autoplay? })` →
  `{ RiveComponent, rive, manifest, inputs, error }`.
- `InputHandle` — `{ key, info, value, set(v), fire() }`. `set()` on a trigger and
  `fire()` on a non-trigger warn in development and no-op; neither throws.
- Components: `RiveStage`, `ErrorPanel`, `ManifestTree`, `InputControls`.

## Design notes

**Why enumeration lives in the controller, not the loader.** The Rive runtime
declares `contents` on the `Rive` class — the mounted instance — not on `RiveFile`.
`RiveFile` has no enumeration path at all; its only artboard accessor,
`getArtboard(name)`, needs a name you do not have yet. So the manifest can only
come from a mounted instance. `useRiveSource` loads; `useRiveController` enumerates.

**Why `useRiveSource` and not `useRiveFile`.** `@rive-app/react-webgl2` already
exports a `useRiveFile`, which this package consumes internally. A same-named
export with a different shape would be a trap one import line away.

**Why core has no dependencies.** `RiveContentsLike` mirrors the runtime's
`RiveFileContents` structurally instead of importing it. TypeScript's structural
typing makes them compatible while keeping core loadable anywhere — including a
an embedded artifact target, where a strict CSP blocks external hosts and everything
must be inlined.

## Tests

```bash
npm test                       # 16 unit tests (pure logic)
npm run typecheck
npx playwright test --workspace apps/studio   # 3 E2E against real .riv files
```

Unit tests cover only the pure layer. The hooks own WASM and a canvas, so mocking
them would test the mock — they are verified in a real browser instead.
