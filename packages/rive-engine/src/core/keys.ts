/**
 * Stable identity for one input within one artboard/state-machine pair.
 *
 * Handles are keyed with this so a stale handle cannot leak across an artboard
 * or state-machine switch: when the selection changes, every key changes, and
 * React discards the old control rows instead of reusing them.
 *
 * Pure and dependency-free, so it lives in core alongside the domain types.
 */
export function handleKey(
  artboard: string | undefined,
  stateMachine: string | undefined,
  inputName: string,
): string {
  return `${artboard ?? '~'}/${stateMachine ?? '~'}/${inputName}`;
}
