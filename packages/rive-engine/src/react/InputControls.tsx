'use client';

import { useState } from 'react';
import type { InputHandle } from './useRiveController';

function NumberControl({ handle }: { handle: InputHandle }) {
  const [value, setValue] = useState<number>(Number(handle.value ?? 0));
  return (
    <>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        data-testid={`input-number-${handle.info.name}`}
        onChange={(e) => {
          const next = Number(e.target.value);
          setValue(next);
          handle.set(next);
        }}
      />
      <output>{value}</output>
    </>
  );
}

function BooleanControl({ handle }: { handle: InputHandle }) {
  const [checked, setChecked] = useState<boolean>(Boolean(handle.value));
  return (
    <input
      type="checkbox"
      checked={checked}
      data-testid={`input-boolean-${handle.info.name}`}
      onChange={(e) => {
        setChecked(e.target.checked);
        handle.set(e.target.checked);
      }}
    />
  );
}

/**
 * Generates one control per input, dispatched on its kind.
 *
 * Unknown input kinds render read-only with their raw runtime tag rather than
 * being silently dropped (spec 6) - a control we cannot render is still
 * information the user needs.
 */
export function InputControls({ inputs }: { inputs: InputHandle[] }) {
  if (inputs.length === 0) {
    return <p data-testid="no-inputs">This state machine has no inputs.</p>;
  }

  return (
    <ul data-testid="input-controls">
      {inputs.map((handle) => (
        <li key={handle.key}>
          <label>
            {handle.info.name}
            {handle.info.kind === 'boolean' && <BooleanControl handle={handle} />}
            {handle.info.kind === 'number' && <NumberControl handle={handle} />}
            {handle.info.kind === 'trigger' && (
              <button
                type="button"
                data-testid={`input-trigger-${handle.info.name}`}
                onClick={() => handle.fire()}
              >
                Fire
              </button>
            )}
            {handle.info.kind === 'unknown' && (
              <span data-testid={`input-unknown-${handle.info.name}`}>
                unsupported input type ({handle.info.rawType})
              </span>
            )}
          </label>
        </li>
      ))}
    </ul>
  );
}
