'use client';

import type { RiveManifest } from '../core';

export interface Selection {
  artboard: string;
  stateMachine?: string;
}

export interface ManifestTreeProps {
  manifest: RiveManifest | null;
  selected: Selection | null;
  onSelect: (next: Selection) => void;
}

/**
 * Artboards -> state machines -> input counts.
 *
 * An artboard with no state machines is stated explicitly rather than rendered
 * as an empty panel, and its animations are still listed (spec 6).
 */
export function ManifestTree({ manifest, selected, onSelect }: ManifestTreeProps) {
  if (!manifest) return null;

  return (
    <ul data-testid="manifest-tree">
      {manifest.artboards.map((ab) => (
        <li key={ab.name} data-testid="artboard-item">
          <button
            type="button"
            aria-pressed={selected?.artboard === ab.name}
            onClick={() => onSelect({ artboard: ab.name })}
          >
            {ab.name}
            {ab.isDefault ? ' (default)' : ''}
          </button>

          {ab.stateMachines.length === 0 ? (
            <p data-testid="no-state-machines">
              No state machines. Animations: {ab.animations.join(', ') || 'none'}
            </p>
          ) : (
            <ul>
              {ab.stateMachines.map((sm) => (
                <li key={sm.name}>
                  <button
                    type="button"
                    data-testid="state-machine-item"
                    aria-pressed={
                      selected?.artboard === ab.name && selected?.stateMachine === sm.name
                    }
                    onClick={() => onSelect({ artboard: ab.name, stateMachine: sm.name })}
                  >
                    {sm.name} ({sm.inputs.length} inputs)
                  </button>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
