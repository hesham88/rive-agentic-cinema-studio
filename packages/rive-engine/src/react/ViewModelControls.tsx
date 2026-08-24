'use client';

import type { ViewModelHandle } from './useViewModelControls';

function NumberControl({ handle }: { handle: ViewModelHandle }) {
  const value = Number(handle.value ?? 0);
  return (
    <>
      <input
        type="number"
        step="any"
        value={value}
        data-testid={`vm-number-${handle.info.name}`}
        onChange={(e) => handle.set(Number(e.target.value))}
      />
      <input
        type="range"
        min={0}
        max={100}
        step={0.5}
        value={Math.min(100, Math.max(0, value))}
        aria-label={`${handle.info.name} slider`}
        onChange={(e) => handle.set(Number(e.target.value))}
      />
    </>
  );
}

/**
 * Controls for view-model-bound properties — Rive's data-binding input system.
 *
 * Rendered alongside `InputControls` (classic state-machine inputs), because a
 * file may use either system or both, and the two do not overlap.
 */
export function ViewModelControls({
  viewModelName,
  handles,
}: {
  viewModelName: string | null;
  handles: ViewModelHandle[];
}) {
  if (!viewModelName) return null;

  if (handles.length === 0) {
    return (
      <p data-testid="no-vm-properties">
        View model &ldquo;{viewModelName}&rdquo; exposes no settable properties.
      </p>
    );
  }

  return (
    <section data-testid="vm-controls" data-viewmodel={viewModelName}>
      <h3>{viewModelName}</h3>
      <ul>
        {handles.map((handle) => (
          <li key={handle.key} data-testid={`vm-row-${handle.info.name}`}>
            <label>
              {handle.info.name}
              {handle.info.kind === 'boolean' && (
                <input
                  type="checkbox"
                  checked={Boolean(handle.value)}
                  data-testid={`vm-boolean-${handle.info.name}`}
                  onChange={(e) => handle.set(e.target.checked)}
                />
              )}
              {handle.info.kind === 'number' && <NumberControl handle={handle} />}
              {handle.info.kind === 'string' && (
                <input
                  type="text"
                  value={String(handle.value ?? '')}
                  data-testid={`vm-string-${handle.info.name}`}
                  onChange={(e) => handle.set(e.target.value)}
                />
              )}
              {handle.info.kind === 'enum' && (
                <select
                  value={String(handle.value ?? '')}
                  data-testid={`vm-enum-${handle.info.name}`}
                  onChange={(e) => handle.set(e.target.value)}
                >
                  {handle.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              )}
              {handle.info.kind === 'trigger' && (
                <button
                  type="button"
                  data-testid={`vm-trigger-${handle.info.name}`}
                  onClick={() => handle.fire()}
                >
                  Fire
                </button>
              )}
              {handle.info.kind === 'color' && (
                <span data-testid={`vm-color-${handle.info.name}`}>
                  color ({String(handle.value ?? '—')})
                </span>
              )}
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
