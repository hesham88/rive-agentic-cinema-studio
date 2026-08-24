'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Rive } from '@rive-app/webgl2';
import {
  inspectViewModelProperties,
  type ViewModelPropertyInfo,
  type ViewModelPropertyLike,
} from '../core';

/**
 * A live handle onto one view model property.
 *
 * Deliberately the same shape as `InputHandle` from `useRiveController`, so a
 * consumer can render either system with one control component.
 */
export interface ViewModelHandle {
  key: string;
  info: ViewModelPropertyInfo;
  value: boolean | number | string | undefined;
  /** Enum properties expose their allowed values; empty for every other kind. */
  options: string[];
  set(next: boolean | number | string): void;
  fire(): void;
}

export interface ViewModelControlsState {
  /** Name of the bound view model, or null when the file uses none. */
  viewModelName: string | null;
  properties: ViewModelPropertyInfo[];
  handles: ViewModelHandle[];
}

function warn(message: string): void {
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.warn(`[rive-engine] ${message}`);
  }
}

/**
 * Enumerates the view model bound to a live Rive instance and returns typed,
 * settable handles for its properties.
 *
 * This is the second half of Rive's input story. `useRiveController` reads
 * classic state-machine inputs; a file authored with data binding has none of
 * those, and everything that drives it lives here instead.
 *
 * REQUIRES the instance to have been created with `autoBind: true`. That flag
 * is false by default, and when it is off `rive.viewModelInstance` is null, so
 * this hook returns zero properties for a file that is in fact fully bound —
 * a wrong answer that looks like a correct one. `useRiveController` sets it.
 *
 * `generation` lets a caller force re-enumeration after the instance
 * re-initialises (the `rive` object keeps its identity across load/reset).
 */
export function useViewModelControls(
  rive: Rive | null,
  generation = 0,
): ViewModelControlsState {
  // Bumped locally so a `set()` re-renders with the new value.
  const [tick, setTick] = useState(0);

  /**
   * The instance bound to the CURRENT artboard, falling back to the file's
   * default view model.
   *
   * This distinction matters in a multi-artboard file: `defaultViewModel()`
   * returns the file-level default, so selecting a second artboard would keep
   * showing the first artboard's properties. `rive.viewModelInstance` is what
   * is actually bound to the artboard on screen.
   */
  const instance = useMemo(() => {
    if (!rive) return null;
    try {
      return rive.viewModelInstance ?? rive.defaultViewModel()?.instance() ?? null;
    } catch (err) {
      warn(`could not resolve a view model instance: ${String(err)}`);
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rive, generation]);

  // Read properties from the INSTANCE, not from a ViewModel definition — the
  // instance is the one that belongs to this artboard.
  const properties = useMemo(() => {
    if (!instance) return [];
    try {
      return inspectViewModelProperties(
        instance.properties as unknown as ViewModelPropertyLike[],
      );
    } catch (err) {
      warn(`could not enumerate view model properties: ${String(err)}`);
      return [];
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instance, generation]);

  const viewModelName = useMemo(() => {
    if (!instance) return null;
    try {
      return instance.viewModelName ?? null;
    } catch {
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instance, generation]);

  const bump = useCallback(() => setTick((t) => t + 1), []);

  // Rive coalesces property changes; ask the instance to flush callbacks each
  // frame so externally-driven values (a listener firing on hover) show up.
  useEffect(() => {
    if (!instance) return;
    let raf = 0;
    const pump = () => {
      try {
        instance.handleCallbacks();
      } catch {
        /* instance torn down */
      }
      raf = requestAnimationFrame(pump);
    };
    raf = requestAnimationFrame(pump);
    return () => cancelAnimationFrame(raf);
  }, [instance]);

  const handles = useMemo<ViewModelHandle[]>(() => {
    if (!instance) return [];
    void tick;

    const out: ViewModelHandle[] = [];
    for (const info of properties) {
      if (!info.writable) continue;
      try {
        const key = `vm/${info.path}`;
        if (info.kind === 'trigger') {
          const t = instance.trigger(info.path);
          if (!t) continue;
          out.push({
            key, info, value: undefined, options: [],
            set() { warn(`set() on trigger "${info.name}"; use fire().`); },
            fire() { t.trigger(); bump(); },
          });
          continue;
        }

        const prop =
          info.kind === 'boolean' ? instance.boolean(info.path)
          : info.kind === 'number' ? instance.number(info.path)
          : info.kind === 'string' ? instance.string(info.path)
          : info.kind === 'enum' ? instance.enum(info.path)
          : info.kind === 'color' ? instance.color(info.path)
          : null;

        if (!prop) continue;

        const options =
          info.kind === 'enum'
            ? ((prop as unknown as { values?: string[] }).values ?? [])
            : [];

        out.push({
          key,
          info,
          value: (prop as unknown as { value?: boolean | number | string }).value,
          options,
          set(next) {
            try {
              (prop as unknown as { value: unknown }).value = next;
              bump();
            } catch (err) {
              warn(`could not set "${info.path}": ${String(err)}`);
            }
          },
          fire() { warn(`fire() on ${info.kind} "${info.name}"; use set().`); },
        });
      } catch (err) {
        warn(`could not bind view model property "${info.path}": ${String(err)}`);
      }
    }
    return out;
  }, [instance, properties, tick, bump]);

  return { viewModelName, properties, handles };
}
