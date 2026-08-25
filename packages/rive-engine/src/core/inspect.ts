import {
  RIVE_INPUT_TYPE,
  type RiveLoadError,
  type ArtboardInfo,
  type InputInfo,
  type RiveContentsLike,
  type RiveInputKind,
  type RiveManifest,
  type StateMachineInfo,
} from './types';

type RawArtboard = NonNullable<RiveContentsLike['artboards']>[number];
type RawStateMachine = NonNullable<RawArtboard['stateMachines']>[number];
type RawInput = NonNullable<RawStateMachine['inputs']>[number];

/**
 * Map a runtime input type constant to its name.
 *
 * Exported because the React layer needs exactly this mapping too, and had its
 * own second copy of the switch. Two implementations of one lookup drift, and
 * the drift shows up as an input driven with the wrong API.
 */
export function inputKind(type: number | undefined): RiveInputKind {
  switch (type) {
    case RIVE_INPUT_TYPE.Boolean:
      return 'boolean';
    case RIVE_INPUT_TYPE.Number:
      return 'number';
    case RIVE_INPUT_TYPE.Trigger:
      return 'trigger';
    default:
      return 'unknown';
  }
}

function toInput(raw: RawInput): InputInfo {
  const kind = inputKind(raw.type);
  const info: InputInfo = { name: raw.name ?? '(unnamed input)', kind };
  if (raw.initialValue !== undefined) info.initialValue = raw.initialValue;
  if (kind === 'unknown' && raw.type !== undefined) info.rawType = raw.type;
  return info;
}

/**
 * Maps the Rive runtime's `rive.contents` structure to our domain manifest.
 * Pure: no React, no canvas, no I/O. This is what makes enumeration testable.
 */
export function inspectRiveContents(contents: RiveContentsLike): RiveManifest {
  const artboards: ArtboardInfo[] = (contents.artboards ?? []).map((ab, index) => {
    const stateMachines: StateMachineInfo[] = (ab.stateMachines ?? []).map((sm) => ({
      name: sm.name ?? '(unnamed state machine)',
      inputs: (sm.inputs ?? []).map(toInput),
    }));
    return {
      name: ab.name ?? '(unnamed artboard)',
      isDefault: index === 0,
      animations: ab.animations ?? [],
      stateMachines,
    };
  });

  return {
    artboards,
    defaultArtboard: artboards[0]?.name ?? null,
  };
}


/**
 * Describe a failure to read a state machine's inputs.
 *
 * Pure, so the hook does not have to decide this mid-render. `undefined` back
 * from `stateMachineInputs` is a genuine failure, and reporting it as "no
 * inputs" would render an empty panel that looks deliberate.
 */
export function stateMachineInputError(
  stateMachine: string,
  cause: 'not-instanced' | unknown,
): RiveLoadError {
  if (cause === 'not-instanced') {
    return {
      kind: 'parse',
      message: `State machine "${stateMachine}" is not instanced, so its inputs cannot be read.`,
    };
  }
  return {
    kind: 'parse',
    message: `Could not read inputs for state machine "${stateMachine}": ${String(cause)}`,
  };
}
