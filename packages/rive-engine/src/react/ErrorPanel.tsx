'use client';

import type { RiveLoadError } from '../core';

const TITLES: Record<RiveLoadError['kind'], string> = {
  parse: 'This file could not be parsed',
  wasm: 'The Rive engine failed to load',
  network: 'The file could not be fetched',
  empty: 'This file contains no artboards',
};

const HINTS: Record<RiveLoadError['kind'], string> = {
  parse: 'The file may be corrupt, or may not be a .riv file.',
  wasm: 'The Rive WebAssembly module did not load. Check that it is served correctly and not blocked.',
  network: 'Check the URL and that the file is reachable.',
  empty: 'Open it in the Rive editor to confirm it exports at least one artboard.',
};

/**
 * Every load failure gets an explicit surface. A blank canvas is never an
 * acceptable outcome (spec 6), so the raw message is always shown alongside
 * the human-readable title.
 */
export function ErrorPanel({ error }: { error: RiveLoadError | null }) {
  if (!error) return null;

  return (
    <div role="alert" data-testid="rive-error" data-error-kind={error.kind}>
      <strong>{TITLES[error.kind]}</strong>
      <p>{HINTS[error.kind]}</p>
      <pre data-testid="rive-error-message">{error.message}</pre>
    </div>
  );
}
