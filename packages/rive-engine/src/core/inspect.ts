import {
  RIVE_INPUT_TYPE,
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

function toKind(type: number | undefined): RiveInputKind {
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
  const kind = toKind(raw.type);
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
