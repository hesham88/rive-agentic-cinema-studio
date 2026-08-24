/**
 * View model domain types and the pure mapper for them.
 *
 * Rive has TWO input systems and they do not overlap:
 *
 *   1. Classic state-machine inputs — boolean/number/trigger, read via
 *      `rive.stateMachineInputs(name)`. See `inspect.ts`.
 *   2. View model properties + data binding — the modern path. This is what the
 *      editor's listeners and transition conditions actually use, and these do
 *      NOT appear in `stateMachineInputs()`.
 *
 * A file authored with data binding therefore enumerates a state machine with
 * ZERO inputs while being fully interactive. This module covers system 2.
 *
 * Pure and dependency-free, like the rest of `core`.
 */

export type ViewModelPropertyKind =
  | 'boolean'
  | 'number'
  | 'string'
  | 'color'
  | 'enum'
  | 'trigger'
  | 'list'
  | 'image'
  | 'artboard'
  | 'viewModel'
  | 'unknown';

/**
 * Rive's `DataType` string enum, mapped to our domain kinds.
 *
 * `integer` and `listIndex` both collapse to 'number': they are numeric to a
 * consumer, and the runtime exposes them through `instance.number(path)`.
 */
const DATA_TYPE_TO_KIND: Record<string, ViewModelPropertyKind> = {
  boolean: 'boolean',
  number: 'number',
  integer: 'number',
  listIndex: 'number',
  string: 'string',
  color: 'color',
  enumType: 'enum',
  trigger: 'trigger',
  list: 'list',
  image: 'image',
  artboard: 'artboard',
  viewModel: 'viewModel',
};

export interface ViewModelPropertyInfo {
  name: string;
  kind: ViewModelPropertyKind;
  /** Path used to address the property on an instance. Nested paths use '/'. */
  path: string;
  /** Present for enum properties: the name of the backing DataEnum. */
  enumName?: string;
  /** Raw runtime DataType, retained for diagnostics when kind is 'unknown'. */
  rawType?: string;
  /** True when this property can be driven from code (has a settable value). */
  writable: boolean;
}

export interface ViewModelInfo {
  name: string;
  properties: ViewModelPropertyInfo[];
  instanceNames: string[];
}

/** Structural mirror of the runtime's ViewModelProperty; core imports nothing. */
export interface ViewModelPropertyLike {
  name?: string;
  type?: string;
  enumName?: string;
}

/** Kinds a consumer can meaningfully set from code. */
const WRITABLE: ReadonlySet<ViewModelPropertyKind> = new Set([
  'boolean',
  'number',
  'string',
  'color',
  'enum',
  'trigger',
]);

export function viewModelKindOf(dataType: string | undefined): ViewModelPropertyKind {
  if (!dataType) return 'unknown';
  return DATA_TYPE_TO_KIND[dataType] ?? 'unknown';
}

/**
 * Maps a runtime view model's `properties` array to our domain shape.
 *
 * Pure: no React, no runtime, no I/O — the same boundary that makes
 * `inspectRiveContents` testable.
 *
 * `parentPath` prefixes nested view model properties so the resulting `path` can
 * be handed straight to `instance.boolean(path)` and friends.
 */
export function inspectViewModelProperties(
  properties: readonly ViewModelPropertyLike[] | undefined,
  parentPath = '',
): ViewModelPropertyInfo[] {
  return (properties ?? []).map((p) => {
    const name = p.name ?? '(unnamed property)';
    const kind = viewModelKindOf(p.type);
    const info: ViewModelPropertyInfo = {
      name,
      kind,
      path: parentPath ? `${parentPath}/${name}` : name,
      writable: WRITABLE.has(kind),
    };
    if (p.enumName) info.enumName = p.enumName;
    if (kind === 'unknown' && p.type) info.rawType = p.type;
    return info;
  });
}
