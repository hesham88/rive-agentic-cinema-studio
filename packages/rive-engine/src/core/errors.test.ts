import { describe, it, expect } from 'vitest';
import { classifyLoadError } from './errors';

describe('classifyLoadError', () => {
  it('classifies WASM failures by message', () => {
    const e = classifyLoadError(new Error('failed to load rive.wasm'));
    expect(e.kind).toBe('wasm');
  });

  it('classifies fetch failures as network', () => {
    const e = classifyLoadError(new Error('Failed to fetch'));
    expect(e.kind).toBe('network');
  });

  it('defaults to parse and preserves the original message verbatim', () => {
    const e = classifyLoadError(new Error('Bad header'));
    expect(e.kind).toBe('parse');
    expect(e.message).toBe('Bad header');
  });

  it('handles non-Error throwables without losing information', () => {
    const e = classifyLoadError('something odd');
    expect(e.kind).toBe('parse');
    expect(e.message).toBe('something odd');
  });

  it('is case-insensitive when matching WASM failures', () => {
    expect(classifyLoadError(new Error('WASM module missing')).kind).toBe('wasm');
  });
});
