import { describe, expect, it } from 'vitest';
import { ByteWriter, FieldType, writeToc } from './writer';

/**
 * These assert the exact bytes, not "it produced something".
 *
 * The whole spike rests on the primitives being byte-correct — a varint that is
 * one byte off produces a file that fails to load with no diagnostic, and no
 * amount of higher-level testing localises it.
 */

const hex = (u: Uint8Array) => [...u].map((b) => b.toString(16).padStart(2, '0')).join(' ');

describe('varUint (LEB128)', () => {
  it('encodes single-byte values as themselves', () => {
    for (const v of [0, 1, 2, 63, 127]) {
      const w = new ByteWriter();
      w.varUint(v);
      expect(hex(w.toUint8Array())).toBe(v.toString(16).padStart(2, '0'));
    }
  });

  it('encodes 128 as 0x80 0x01 — the classic boundary', () => {
    const w = new ByteWriter();
    w.varUint(128);
    expect(hex(w.toUint8Array())).toBe('80 01');
  });

  it('encodes known LEB128 vectors', () => {
    const cases: Array<[number, string]> = [
      [300, 'ac 02'],
      [624485, 'e5 8e 26'],
      [16384, '80 80 01'],
      [2097151, 'ff ff 7f'],
    ];
    for (const [value, expected] of cases) {
      const w = new ByteWriter();
      w.varUint(value);
      expect(hex(w.toUint8Array()), `varUint(${value})`).toBe(expected);
    }
  });

  it('sets the continuation bit on every byte but the last', () => {
    const w = new ByteWriter();
    w.varUint(624485);
    const out = w.toUint8Array();
    for (let i = 0; i < out.length - 1; i += 1) {
      expect(out[i]! & 0x80, `byte ${i} must continue`).toBe(0x80);
    }
    expect(out[out.length - 1]! & 0x80).toBe(0);
  });

  it('rejects negatives and non-finite values', () => {
    const w = new ByteWriter();
    expect(() => w.varUint(-1)).toThrow(RangeError);
    expect(() => w.varUint(NaN)).toThrow(RangeError);
    expect(() => w.varUint(Infinity)).toThrow(RangeError);
  });

  it('handles values beyond 32 bits without bit-shift corruption', () => {
    // `v >> 7` would go wrong above 2^31; the implementation divides instead.
    const w = new ByteWriter();
    w.varUint(2 ** 40);
    const out = w.toUint8Array();
    expect(out.length).toBe(6);
    let decoded = 0;
    for (let i = out.length - 1; i >= 0; i -= 1) decoded = decoded * 128 + (out[i]! & 0x7f);
    expect(decoded).toBe(2 ** 40);
  });
});

describe('fixed-width primitives', () => {
  it('writes uint32 little endian', () => {
    const w = new ByteWriter();
    w.uint32(0x11223344);
    expect(hex(w.toUint8Array())).toBe('44 33 22 11');
  });

  it('writes float32 little endian', () => {
    const w = new ByteWriter();
    w.float(1);
    expect(hex(w.toUint8Array())).toBe('00 00 80 3f');
  });

  it('round-trips floats through a DataView', () => {
    const w = new ByteWriter();
    for (const v of [0, -1, 0.5, 100, 68, 36, -12.25]) w.float(v);
    const out = w.toUint8Array();
    const view = new DataView(out.buffer, out.byteOffset, out.byteLength);
    [0, -1, 0.5, 100, 68, 36, -12.25].forEach((v, i) => {
      expect(view.getFloat32(i * 4, true)).toBeCloseTo(v, 5);
    });
  });

  it('writes a bool as ONE byte, not a varint', () => {
    // CoreBoolType::deserialize calls readByte(). A varint would coincidentally
    // agree for 0/1 but this pins the intent.
    const t = new ByteWriter();
    t.bool(true);
    expect(hex(t.toUint8Array())).toBe('01');
    expect(t.length).toBe(1);
    const f = new ByteWriter();
    f.bool(false);
    expect(hex(f.toUint8Array())).toBe('00');
  });

  it('writes strings as varuint BYTE length then utf-8', () => {
    const w = new ByteWriter();
    w.string('ab');
    expect(hex(w.toUint8Array())).toBe('02 61 62');
  });

  it('counts bytes, not code points, for multi-byte text', () => {
    const w = new ByteWriter();
    w.string('é'); // 2 bytes in UTF-8
    const out = w.toUint8Array();
    expect(out[0]).toBe(2);
    expect(out.length).toBe(3);
  });

  it('writes an empty string as a zero length', () => {
    const w = new ByteWriter();
    w.string('');
    expect(hex(w.toUint8Array())).toBe('00');
  });

  it('grows past its initial capacity without corrupting earlier bytes', () => {
    const w = new ByteWriter(4);
    for (let i = 0; i < 500; i += 1) w.byte(i & 0xff);
    const out = w.toUint8Array();
    expect(out.length).toBe(500);
    expect(out[0]).toBe(0);
    expect(out[499]).toBe(499 & 0xff);
  });
});

describe('table of contents', () => {
  it('packs FOUR field ids per uint32, not sixteen', () => {
    // RuntimeHeader::read walks currentBit 0,2,4,6 then refetches at 8 — so the
    // upper 24 bits of every word are padding. Packing densely produces a file
    // that will not load, which is why this test exists.
    const w = new ByteWriter();
    const fields = new Map([
      [1, FieldType.uint],
      [2, FieldType.string],
      [3, FieldType.double],
      [4, FieldType.color],
      [5, FieldType.uint],
    ]);
    writeToc(w, fields);
    const out = w.toUint8Array();
    // keys 1..5 then terminator 0 = 6 bytes, then 2 uint32 words for 5 keys.
    expect(out.length).toBe(6 + 8);
  });

  it('lays the two-bit codes out low-order first', () => {
    const w = new ByteWriter();
    writeToc(
      w,
      new Map([
        [1, FieldType.uint], // 0 -> bits 0-1
        [2, FieldType.string], // 1 -> bits 2-3
        [3, FieldType.double], // 2 -> bits 4-5
        [4, FieldType.color], // 3 -> bits 6-7
      ]),
    );
    const out = w.toUint8Array();
    const view = new DataView(out.buffer, out.byteOffset, out.byteLength);
    const word = view.getUint32(5, true); // after 4 keys + terminator
    expect(word & 3).toBe(0);
    expect((word >> 2) & 3).toBe(1);
    expect((word >> 4) & 3).toBe(2);
    expect((word >> 6) & 3).toBe(3);
    expect(word >>> 8).toBe(0); // upper 24 bits are padding
  });

  it('terminates the key list with a zero varint', () => {
    const w = new ByteWriter();
    writeToc(w, new Map([[7, FieldType.double]]));
    const out = w.toUint8Array();
    expect(out[0]).toBe(7);
    expect(out[1]).toBe(0);
  });

  it('emits keys in ascending order', () => {
    const w = new ByteWriter();
    writeToc(
      w,
      new Map([
        [20, FieldType.double],
        [4, FieldType.string],
        [13, FieldType.double],
      ]),
    );
    const out = w.toUint8Array();
    expect([out[0], out[1], out[2], out[3]]).toEqual([4, 13, 20, 0]);
  });

  it('refuses to declare key 0, which is the object terminator', () => {
    const w = new ByteWriter();
    expect(() => writeToc(w, new Map([[0, FieldType.uint]]))).toThrow(RangeError);
  });

  it('writes one word even for a single property', () => {
    const w = new ByteWriter();
    writeToc(w, new Map([[13, FieldType.double]]));
    expect(w.toUint8Array().length).toBe(2 + 4);
  });
});
