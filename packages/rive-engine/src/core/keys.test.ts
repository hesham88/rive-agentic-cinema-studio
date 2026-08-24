import { describe, it, expect } from 'vitest';
import { handleKey } from './keys';

describe('handleKey', () => {
  it('composes artboard, state machine, and input into one key', () => {
    expect(handleKey('Main', 'SM', 'on')).toBe('Main/SM/on');
  });

  it('distinguishes same-named inputs across artboards', () => {
    expect(handleKey('A', 'SM', 'go')).not.toBe(handleKey('B', 'SM', 'go'));
  });

  it('distinguishes same-named inputs across state machines', () => {
    expect(handleKey('A', 'One', 'go')).not.toBe(handleKey('A', 'Two', 'go'));
  });

  it('substitutes a placeholder for undefined segments', () => {
    expect(handleKey(undefined, undefined, 'on')).toBe('~/~/on');
  });
});
