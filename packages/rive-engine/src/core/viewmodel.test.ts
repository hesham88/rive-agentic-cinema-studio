import { describe, it, expect } from 'vitest';
import { inspectViewModelProperties, viewModelKindOf } from './viewmodel';

describe('viewModelKindOf', () => {
  it('maps every DataType the runtime emits', () => {
    expect(viewModelKindOf('boolean')).toBe('boolean');
    expect(viewModelKindOf('number')).toBe('number');
    expect(viewModelKindOf('string')).toBe('string');
    expect(viewModelKindOf('color')).toBe('color');
    expect(viewModelKindOf('enumType')).toBe('enum');
    expect(viewModelKindOf('trigger')).toBe('trigger');
    expect(viewModelKindOf('list')).toBe('list');
    expect(viewModelKindOf('image')).toBe('image');
    expect(viewModelKindOf('artboard')).toBe('artboard');
    expect(viewModelKindOf('viewModel')).toBe('viewModel');
  });

  it('collapses integer and listIndex to number', () => {
    // Both are numeric to a consumer and are read via instance.number(path).
    expect(viewModelKindOf('integer')).toBe('number');
    expect(viewModelKindOf('listIndex')).toBe('number');
  });

  it('returns unknown for unrecognised or missing types', () => {
    expect(viewModelKindOf('somethingNew')).toBe('unknown');
    expect(viewModelKindOf(undefined)).toBe('unknown');
    expect(viewModelKindOf('none')).toBe('unknown');
  });
});

describe('inspectViewModelProperties', () => {
  it('maps names, kinds, and paths', () => {
    const props = inspectViewModelProperties([
      { name: 'isHovered', type: 'boolean' },
      { name: 'boost', type: 'number' },
    ]);
    expect(props.map((p) => [p.name, p.kind, p.path])).toEqual([
      ['isHovered', 'boolean', 'isHovered'],
      ['boost', 'number', 'boost'],
    ]);
  });

  it('marks settable kinds writable and structural kinds not', () => {
    const props = inspectViewModelProperties([
      { name: 'a', type: 'boolean' },
      { name: 'b', type: 'trigger' },
      { name: 'c', type: 'viewModel' },
      { name: 'd', type: 'list' },
    ]);
    expect(props.map((p) => p.writable)).toEqual([true, true, false, false]);
  });

  it('prefixes nested paths so they address the instance directly', () => {
    const props = inspectViewModelProperties([{ name: 'speed', type: 'number' }], 'engine');
    expect(props[0]!.path).toBe('engine/speed');
  });

  it('retains the enum name', () => {
    const props = inspectViewModelProperties([
      { name: 'mood', type: 'enumType', enumName: 'Moods' },
    ]);
    expect(props[0]!.kind).toBe('enum');
    expect(props[0]!.enumName).toBe('Moods');
  });

  it('keeps unknown types with their raw tag rather than dropping them', () => {
    const props = inspectViewModelProperties([{ name: 'mystery', type: 'futureType' }]);
    expect(props[0]!.kind).toBe('unknown');
    expect(props[0]!.rawType).toBe('futureType');
    expect(props[0]!.writable).toBe(false);
  });

  it('tolerates missing names and empty input', () => {
    expect(inspectViewModelProperties(undefined)).toEqual([]);
    expect(inspectViewModelProperties([])).toEqual([]);
    expect(inspectViewModelProperties([{ type: 'boolean' }])[0]!.name).toBe(
      '(unnamed property)',
    );
  });
});
