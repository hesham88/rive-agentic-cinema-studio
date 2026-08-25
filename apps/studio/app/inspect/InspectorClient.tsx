'use client';

import { useState } from 'react';
import {
  ErrorPanel,
  InputControls,
  ManifestTree,
  RiveStage,
  useKeyboardBindings,
  useRiveController,
  useRiveSource,
  useViewModelControls,
  ViewModelControls,
  type RiveSource,
  type Selection,
} from 'rive-engine/react';
import { AuthControl } from '../AuthControl';

/**
 * Loads one source and owns the single Rive instance for it.
 *
 * Mounted only once a source exists, and keyed by that source. Two reasons:
 *
 *  - `useRiveFile` (the runtime's own hook, used inside `useRiveSource`)
 *    constructs a `RiveFile` unconditionally, and its `init()` throws
 *    "Rive source file or data buffer required" when given neither src nor
 *    buffer. That rejection is unhandled and surfaced as a page error on every
 *    visit — caught by the production smoke test. Not calling the hook until
 *    there is something to load is the fix; hooks cannot be conditional, so the
 *    condition lives here at the component boundary.
 *  - Keying by source guarantees a genuinely fresh Rive instance per file
 *    rather than a reused one.
 */
function RiveWorkspace({ source }: { source: RiveSource }) {
  const [selected, setSelected] = useState<Selection | null>(null);

  const { riveFile, error: loadError, status } = useRiveSource(source);

  // ONE controller for the page. Its RiveComponent is handed to RiveStage;
  // calling useRiveController again there would mount a second Rive instance,
  // and the one without a rendered canvas would never load.
  const {
    RiveComponent,
    rive,
    manifest,
    inputs,
    error: contentError,
    generation,
  } = useRiveController({
    riveFile,
    artboard: selected?.artboard,
    stateMachine: selected?.stateMachine,
  });

  // Rive's second input system: view-model properties via data binding. A file
  // authored that way has zero classic state-machine inputs.
  // `generation` is required, not optional: `rive` keeps its object identity
  // across a reset, so without it the panel keeps showing the FIRST artboard's
  // view model after every subsequent selection.
  const { viewModelName, handles } = useViewModelControls(rive, generation);

  // Rive's format has no keyboard listener, so keys are driven from the runtime
  // into view-model properties, which the state machine's conditions react to.
  useKeyboardBindings(handles, [
    { key: 'h', property: 'isHovered', whileHeld: true, onRelease: false },
    { key: 'ArrowUp', property: 'boost', rampBy: 60, min: 0, max: 100 },
    { key: 'ArrowDown', property: 'boost', rampBy: -60, min: 0, max: 100 },
  ]);

  return (
    <>
      <p data-testid="status" className="text-xs uppercase tracking-wide opacity-60">
        {loadError ? 'error' : manifest ? 'ready' : status}
      </p>

      <ErrorPanel error={loadError ?? contentError} />

      <div className="grid gap-6 md:grid-cols-[minmax(0,18rem)_1fr]">
        <aside>
          <ManifestTree manifest={manifest} selected={selected} onSelect={setSelected} />
        </aside>

        <section className="flex flex-col gap-4">
          <RiveStage component={RiveComponent} className="aspect-video w-full rounded border" />
          {selected?.stateMachine ? <InputControls inputs={inputs} /> : null}
          <ViewModelControls viewModelName={viewModelName} handles={handles} />
        </section>
      </div>
    </>
  );
}

export function InspectorClient() {
  const [source, setSource] = useState<RiveSource | null>(null);
  const [sourceId, setSourceId] = useState(0);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <header className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-2xl font-semibold">Rive Inspector</h1>
          <p className="text-sm opacity-70">
            Load a .riv file to enumerate its artboards, state machines, and inputs.
          </p>
        </div>
        <AuthControl />
      </header>

      <input
        type="file"
        accept=".riv"
        data-testid="file-input"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          setSource({ kind: 'buffer', buffer: await file.arrayBuffer() });
          setSourceId((n) => n + 1);
        }}
      />

      {source ? (
        <RiveWorkspace key={sourceId} source={source} />
      ) : (
        <p data-testid="status" className="text-xs uppercase tracking-wide opacity-60">
          idle
        </p>
      )}
    </main>
  );
}
