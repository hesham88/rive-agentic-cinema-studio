import { describe, it, expect } from 'vitest';
import { inspectRiveContents } from './inspect';
import { RIVE_INPUT_TYPE } from './types';

describe('inspectRiveContents', () => {
  it('maps a single artboard and marks it default', () => {
    const m = inspectRiveContents({
      artboards: [{ name: 'Main', animations: ['idle'], stateMachines: [] }],
    });
    expect(m.artboards).toHaveLength(1);
    expect(m.artboards[0]!.name).toBe('Main');
    expect(m.artboards[0]!.isDefault).toBe(true);
    expect(m.artboards[0]!.animations).toEqual(['idle']);
    expect(m.defaultArtboard).toBe('Main');
  });

  it('marks only the first artboard as default', () => {
    const m = inspectRiveContents({
      artboards: [
        { name: 'A', animations: [], stateMachines: [] },
        { name: 'B', animations: [], stateMachines: [] },
      ],
    });
    expect(m.artboards.map((a) => a.isDefault)).toEqual([true, false]);
    expect(m.defaultArtboard).toBe('A');
  });

  it('maps all three input kinds from their runtime tags', () => {
    const m = inspectRiveContents({
      artboards: [
        {
          name: 'Main',
          animations: [],
          stateMachines: [
            {
              name: 'SM',
              inputs: [
                { name: 'on', type: RIVE_INPUT_TYPE.Boolean, initialValue: true },
                { name: 'speed', type: RIVE_INPUT_TYPE.Number, initialValue: 2 },
                { name: 'go', type: RIVE_INPUT_TYPE.Trigger },
              ],
            },
          ],
        },
      ],
    });
    const inputs = m.artboards[0]!.stateMachines[0]!.inputs;
    expect(inputs.map((i) => i.kind)).toEqual(['boolean', 'number', 'trigger']);
    expect(inputs[0]!.initialValue).toBe(true);
    expect(inputs[1]!.initialValue).toBe(2);
    expect(inputs[2]!.initialValue).toBeUndefined();
  });

  it('retains the raw tag for unknown input types instead of dropping them', () => {
    const m = inspectRiveContents({
      artboards: [
        {
          name: 'Main',
          animations: [],
          stateMachines: [{ name: 'SM', inputs: [{ name: 'mystery', type: 999 }] }],
        },
      ],
    });
    const input = m.artboards[0]!.stateMachines[0]!.inputs[0]!;
    expect(input.kind).toBe('unknown');
    expect(input.rawType).toBe(999);
    expect(input.name).toBe('mystery');
  });

  it('returns an empty manifest for contents with no artboards', () => {
    expect(inspectRiveContents({})).toEqual({ artboards: [], defaultArtboard: null });
    expect(inspectRiveContents({ artboards: [] })).toEqual({
      artboards: [],
      defaultArtboard: null,
    });
  });

  it('tolerates missing names, animations, state machines, and inputs', () => {
    const m = inspectRiveContents({ artboards: [{}] });
    expect(m.artboards[0]!.name).toBe('(unnamed artboard)');
    expect(m.artboards[0]!.animations).toEqual([]);
    expect(m.artboards[0]!.stateMachines).toEqual([]);
  });

  it('handles an artboard with animations but no state machines', () => {
    const m = inspectRiveContents({
      artboards: [{ name: 'Static', animations: ['spin'], stateMachines: [] }],
    });
    expect(m.artboards[0]!.stateMachines).toEqual([]);
    expect(m.artboards[0]!.animations).toEqual(['spin']);
  });
});
