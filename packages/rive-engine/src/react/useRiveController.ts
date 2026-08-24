'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useCanvasResync } from './useCanvasResync';
import { useRive } from '@rive-app/react-webgl2';
import { EventType } from '@rive-app/webgl2';
import type { Rive, RiveFile, StateMachineInput } from '@rive-app/webgl2';
import {
  handleKey,
  inspectRiveContents,
  RIVE_INPUT_TYPE,
  type InputInfo,
  type RiveContentsLike,
  type RiveInputKind,
  type RiveLoadError,
  type RiveManifest,
} from '../core';

export interface InputHandle {
  /** Stable identity: `artboard/stateMachine/inputName`. */
  key: string;
  info: InputInfo;
  value: boolean | number | undefined;
  set(next: boolean | number): void;
  fire(): void;
}

export interface RiveControllerParams {
  riveFile: RiveFile | null;
  artboard?: string;
  stateMachine?: string;
  autoplay?: boolean;
}

export interface RiveControllerState {
  RiveComponent: ReturnType<typeof useRive>['RiveComponent'];
  rive: Rive | null;
  manifest: RiveManifest | null;
  inputs: InputHandle[];
  error: RiveLoadError | null;
  /**
   * Bumped every time the instance re-initialises.
   *
   * MUST be passed to `useViewModelControls`. The `rive` object keeps its
   * identity across `load()` and `reset()`, so anything deriving state from it
   * has no way to know a switch happened — a `useMemo` keyed on `rive` alone
   * silently keeps the previous artboard's view model. That is not theoretical:
   * selecting a second artboard used to show the first one's properties, and
   * both artboards reported identically, which is the tell.
   */
  generation: number;
}

function kindOf(type: number): RiveInputKind {
  if (type === RIVE_INPUT_TYPE.Boolean) return 'boolean';
  if (type === RIVE_INPUT_TYPE.Number) return 'number';
  if (type === RIVE_INPUT_TYPE.Trigger) return 'trigger';
  return 'unknown';
}

function warn(message: string): void {
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.warn(`[rive-engine] ${message}`);
  }
}

/**
 * Mounts a live Rive instance from an already-parsed RiveFile, enumerates the
 * file, and exposes its state-machine inputs as typed handles.
 *
 * This hook owns the ONLY Rive instance. Its `RiveComponent` must be rendered
 * for the canvas to attach — an unrendered component never loads, so `rive`
 * stays null and both `manifest` and `inputs` stay empty. Pass `RiveComponent`
 * down to `RiveStage`; never call this hook twice for one file.
 *
 * Re-initialisation is handled here, imperatively, because `useRive`'s own init
 * effect does not treat `artboard`, `stateMachines`, or `riveFile` as reactive
 * dependencies: once its instance exists, changing those props is a no-op.
 * Consumers therefore do NOT need to force a remount with a `key`.
 */
export function useRiveController(params: RiveControllerParams): RiveControllerState {
  const { riveFile, artboard, stateMachine, autoplay = true } = params;

  const { rive, RiveComponent } = useRive(
    riveFile
      ? {
          riveFile,
          artboard,
          stateMachines: stateMachine,
          autoplay,
          // Required, and NOT the runtime default. `autoBind` is false unless
          // asked, and without it `rive.viewModelInstance` stays null — so a
          // data-bound file reports zero properties and looks inert while
          // being fully interactive. Every re-init below must repeat this.
          //
          // The cost: for an artboard that genuinely has no view model, the
          // runtime logs "Could not find a View Model linked to Artboard X".
          // That is informational, not an error — the load succeeds — and it
          // cannot be suppressed from here. A noisy console beats an inspector
          // that silently under-reports what a file exposes.
          autoBind: true,
        }
      : null,
    { shouldResizeCanvasToContainer: true },
  );

  // Without this the drawing buffer stays at the 300x150 HTML default and
  // the artboard renders into nothing. See useCanvasResync.
  useCanvasResync(rive);

  // Bumped whenever the instance re-initialises. `rive` keeps the same object
  // identity across load/reset, so derived state needs an explicit signal.
  const [generation, setGeneration] = useState(0);
  const bump = useCallback(() => setGeneration((g) => g + 1), []);

  const [inputError, setInputError] = useState<RiveLoadError | null>(null);

  useEffect(() => {
    if (!rive) return;
    rive.on(EventType.Load, bump);
    return () => {
      try {
        rive.off(EventType.Load, bump);
      } catch {
        /* instance already cleaned up */
      }
    };
  }, [rive, bump]);

  // Re-load when the source file changes. Skips the first file, which useRive
  // itself loaded.
  const loadedFile = useRef<RiveFile | null>(null);
  useEffect(() => {
    if (!rive || !riveFile) return;
    if (loadedFile.current === null || loadedFile.current === riveFile) {
      loadedFile.current = riveFile;
      return;
    }
    loadedFile.current = riveFile;
    try {
      rive.load({ riveFile, artboard, stateMachines: stateMachine, autoplay, autoBind: true });
    } catch (err) {
      warn(`could not load the new file: ${String(err)}`);
    }
    // artboard/stateMachine are read but deliberately excluded: a selection
    // change is handled by the reset effect below, not by a full reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rive, riveFile]);

  // Re-instance when the selection changes. Skipped on the first run, since
  // useRive already instanced with these params.
  const appliedSelection = useRef<string | null>(null);
  useEffect(() => {
    if (!rive) return;
    const next = `${artboard ?? ''}/${stateMachine ?? ''}`;
    if (appliedSelection.current === null || appliedSelection.current === next) {
      appliedSelection.current = next;
      return;
    }
    appliedSelection.current = next;
    try {
      rive.reset({ artboard, stateMachines: stateMachine, autoplay, autoBind: true });
      bump();
    } catch (err) {
      warn(`could not switch to "${next}": ${String(err)}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rive, artboard, stateMachine]);

  const manifest = useMemo<RiveManifest | null>(() => {
    if (!rive) return null;
    void generation;
    try {
      const contents = rive.contents as RiveContentsLike | undefined;
      return inspectRiveContents(contents ?? {});
    } catch (err) {
      warn(`could not read file contents: ${String(err)}`);
      return null;
    }
  }, [rive, generation]);

  const wrap = useCallback(
    (raw: StateMachineInput): InputHandle => {
      const kind = kindOf(raw.type as unknown as number);
      const info: InputInfo = { name: raw.name, kind };
      if (kind !== 'trigger') info.initialValue = raw.value;
      if (kind === 'unknown') info.rawType = raw.type as unknown as number;

      return {
        key: handleKey(artboard, stateMachine, raw.name),
        info,
        value: kind === 'trigger' ? undefined : raw.value,
        set(next) {
          if (kind === 'trigger') {
            warn(`set() called on trigger input "${raw.name}"; use fire().`);
            return;
          }
          raw.value = next;
        },
        fire() {
          if (kind !== 'trigger') {
            warn(`fire() called on ${kind} input "${raw.name}"; use set().`);
            return;
          }
          raw.fire();
        },
      };
    },
    [artboard, stateMachine],
  );

  const inputs = useMemo(() => {
    if (!rive || !stateMachine) return [];
    void generation;
    try {
      // Returns undefined when the state machine is not instanced — a real
      // failure that must not be laundered into "this machine has no inputs".
      const raw = rive.stateMachineInputs(stateMachine) as StateMachineInput[] | undefined;
      if (raw === undefined) {
        setInputError({
          kind: 'parse',
          message: `State machine "${stateMachine}" is not instanced, so its inputs cannot be read.`,
        });
        return [];
      }
      setInputError(null);
      return raw.map(wrap);
    } catch (err) {
      setInputError({
        kind: 'parse',
        message: `Could not read inputs for state machine "${stateMachine}": ${String(err)}`,
      });
      return [];
    }
  }, [rive, stateMachine, wrap, generation]);

  const error = useMemo<RiveLoadError | null>(() => {
    if (inputError) return inputError;
    if (!manifest) return null;
    return manifest.artboards.length === 0
      ? { kind: 'empty', message: 'This file contains no artboards.' }
      : null;
  }, [manifest, inputError]);

  return { RiveComponent, rive, manifest, inputs, error, generation };
}
