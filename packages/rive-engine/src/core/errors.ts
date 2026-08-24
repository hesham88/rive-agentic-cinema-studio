import type { RiveLoadError } from './types';

/**
 * Maps an unknown throwable to one of the four RiveLoadError kinds (spec 6).
 *
 * Pure and dependency-free, so it lives in core rather than the React layer:
 * classifying a failure needs no runtime, and keeping it here means it can be
 * unit-tested without importing React or the WASM runtime.
 *
 * The original message is always preserved verbatim — the UI shows it, because
 * a blank canvas with a generic message is worse than a raw parser error.
 */
export function classifyLoadError(err: unknown): RiveLoadError {
  const message = err instanceof Error ? err.message : String(err);
  const lower = message.toLowerCase();
  if (lower.includes('wasm')) return { kind: 'wasm', message };
  if (lower.includes('fetch') || lower.includes('network')) {
    return { kind: 'network', message };
  }
  return { kind: 'parse', message };
}
