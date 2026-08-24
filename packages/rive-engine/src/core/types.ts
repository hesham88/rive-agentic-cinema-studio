/** Input type tags as emitted by @rive-app/webgl2's StateMachineInputType enum. */
export const RIVE_INPUT_TYPE = {
  Number: 56,
  Trigger: 58,
  Boolean: 59,
} as const;

export type RiveInputKind = 'boolean' | 'number' | 'trigger' | 'unknown';

export interface InputInfo {
  name: string;
  kind: RiveInputKind;
  /** Present for boolean and number inputs; undefined for triggers. */
  initialValue?: boolean | number;
  /** Raw runtime type tag, retained for diagnostics when kind is 'unknown'. */
  rawType?: number;
}

export interface StateMachineInfo {
  name: string;
  inputs: InputInfo[];
}

export interface ArtboardInfo {
  name: string;
  isDefault: boolean;
  animations: string[];
  stateMachines: StateMachineInfo[];
}

export interface RiveManifest {
  artboards: ArtboardInfo[];
  /** Name of the default artboard, or null when the file declares none. */
  defaultArtboard: string | null;
}

export type RiveLoadError =
  | { kind: 'parse'; message: string }
  | { kind: 'wasm'; message: string }
  | { kind: 'network'; status?: number; message: string }
  | { kind: 'empty'; message: string };

/**
 * Structural mirror of @rive-app/webgl2's RiveFileContents. Declared here rather
 * than imported so core stays dependency-free (spec 4.1).
 */
export interface RiveContentsLike {
  artboards?: Array<{
    name?: string;
    animations?: string[];
    stateMachines?: Array<{
      name?: string;
      inputs?: Array<{
        name?: string;
        type?: number;
        initialValue?: boolean | number;
      }>;
    }>;
  }>;
}
