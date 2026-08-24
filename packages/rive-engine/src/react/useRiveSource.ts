'use client';

import { useMemo } from 'react';
import { useRiveFile } from '@rive-app/react-webgl2';
import type { RiveFile } from '@rive-app/webgl2';
import type { RiveLoadError } from '../core';

export type RiveSource =
  | { kind: 'url'; url: string }
  | { kind: 'buffer'; buffer: ArrayBuffer };

export type RiveSourceStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface RiveSourceState {
  riveFile: RiveFile | null;
  error: RiveLoadError | null;
  status: RiveSourceStatus;
}

/**
 * Loads a .riv source into a RiveFile and reports load failures.
 *
 * Deliberately does NOT return a manifest. Enumeration requires
 * `rive.contents`, which the runtime exposes only on a MOUNTED `Rive` instance
 * — `RiveFile` offers no equivalent (its only artboard accessor,
 * `getArtboard(name)`, needs a name you do not have yet). The manifest
 * therefore comes from `useRiveController`, which owns that instance.
 *
 * Named `useRiveSource`, not `useRiveFile` — the latter is already exported by
 * @rive-app/react-webgl2 and is consumed internally here.
 */
export function useRiveSource(source: RiveSource | null): RiveSourceState {
  const params = useMemo(() => {
    if (!source) return {};
    return source.kind === 'url' ? { src: source.url } : { buffer: source.buffer };
  }, [source]);

  const { riveFile, status: fileStatus } = useRiveFile(params);

  if (!source) {
    return { riveFile: null, error: null, status: 'idle' };
  }

  if (fileStatus === 'failed') {
    return {
      riveFile: null,
      status: 'error',
      error: {
        kind: source.kind === 'url' ? 'network' : 'parse',
        message: 'Rive could not load this file. It may be corrupt, or not a .riv file.',
      },
    };
  }

  if (fileStatus !== 'success' || !riveFile) {
    return { riveFile: null, error: null, status: 'loading' };
  }

  return { riveFile, error: null, status: 'ready' };
}
