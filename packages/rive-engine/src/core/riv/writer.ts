/**
 * Byte-level primitives for writing a `.riv` file.
 *
 * Every encoding here was read off the C++ runtime's reader
 * (`src/core/binary_reader.cpp`, `src/core/field_types/*.cpp`) rather than from
 * prose, because the published description omits two things that silently
 * produce an unloadable file. Both are called out at their implementation.
 *
 * Zero dependencies, so this runs unchanged in Node and in the browser — which
 * is the point: a studio should be able to emit a `.riv` client-side without a
 * server round-trip.
 */

export class ByteWriter {
  private buf: Uint8Array;
  private len = 0;

  constructor(initial = 1024) {
    this.buf = new Uint8Array(initial);
  }

  private ensure(extra: number): void {
    if (this.len + extra <= this.buf.length) return;
    let next = this.buf.length * 2;
    while (next < this.len + extra) next *= 2;
    const grown = new Uint8Array(next);
    grown.set(this.buf.subarray(0, this.len));
    this.buf = grown;
  }

  get length(): number {
    return this.len;
  }

  byte(v: number): this {
    this.ensure(1);
    this.buf[this.len++] = v & 0xff;
    return this;
  }

  bytes(v: Uint8Array): this {
    this.ensure(v.length);
    this.buf.set(v, this.len);
    this.len += v.length;
    return this;
  }

  /**
   * LEB128 unsigned varint — the format's workhorse.
   *
   * Seven bits per byte, low group first, high bit set on every byte except the
   * last. Object type keys, property keys, lengths and all uint-family values
   * use this.
   */
  varUint(value: number): this {
    if (!Number.isFinite(value) || value < 0) {
      throw new RangeError(`varUint needs a non-negative finite number, got ${value}`);
    }
    let v = Math.floor(value);
    do {
      let seven = v & 0x7f;
      v = Math.floor(v / 128);
      if (v !== 0) seven |= 0x80;
      this.byte(seven);
    } while (v !== 0);
    return this;
  }

  /** 32-bit unsigned, little endian. Used by colors and the ToC bit array. */
  uint32(value: number): this {
    this.ensure(4);
    const v = value >>> 0;
    this.buf[this.len++] = v & 0xff;
    this.buf[this.len++] = (v >>> 8) & 0xff;
    this.buf[this.len++] = (v >>> 16) & 0xff;
    this.buf[this.len++] = (v >>> 24) & 0xff;
    return this;
  }

  /** IEEE-754 float32, little endian. Rive's `double` fields are 32-bit. */
  float(value: number): this {
    this.ensure(4);
    const view = new DataView(this.buf.buffer, this.buf.byteOffset + this.len, 4);
    view.setFloat32(0, value, true);
    this.len += 4;
    return this;
  }

  /**
   * A boolean.
   *
   * ⚠ One raw byte, NOT a varuint — `CoreBoolType::deserialize` calls
   * `readByte()`. It survives being declared as a uint in the table of contents
   * only because 0 and 1 encode identically in both schemes, so a runtime
   * skipping an unknown bool as a varuint still lands on the right offset.
   */
  bool(value: boolean): this {
    return this.byte(value ? 1 : 0);
  }

  /** varuint byte-length, then UTF-8. Note: bytes, not code points. */
  string(value: string): this {
    const utf8 = new TextEncoder().encode(value);
    this.varUint(utf8.length);
    return this.bytes(utf8);
  }

  /** varuint length, then the raw payload. */
  blob(value: Uint8Array): this {
    this.varUint(value.length);
    return this.bytes(value);
  }

  toUint8Array(): Uint8Array {
    return this.buf.slice(0, this.len);
  }
}

/** The four backing types the table of contents can describe, 2 bits each. */
export const FieldType = {
  /** uint, Id, bool, int and every sized integer */
  uint: 0,
  /** String and Bytes — both length-prefixed, so skipping is identical */
  string: 1,
  /** double, written as float32 */
  double: 2,
  /** Color, written as uint32 */
  color: 3,
} as const;

export type FieldTypeId = (typeof FieldType)[keyof typeof FieldType];

/**
 * Write the header's property table of contents.
 *
 * ⚠ The bit array packs **four** field ids per uint32, not sixteen.
 * `RuntimeHeader::read` walks `currentBit` 0 → 2 → 4 → 6 and fetches a fresh
 * `readUint32()` the moment it reaches 8, so only the low byte of each word is
 * ever consulted and the upper 24 bits are padding. Packing them densely — the
 * natural reading of "byte-aligned bit array" — yields a file that fails to
 * load with no useful error.
 */
export function writeToc(w: ByteWriter, fields: ReadonlyMap<number, FieldTypeId>): void {
  const keys = [...fields.keys()].sort((a, b) => a - b);
  for (const k of keys) {
    if (k === 0) throw new RangeError('property key 0 is the terminator and cannot be declared');
    w.varUint(k);
  }
  w.varUint(0);

  for (let i = 0; i < keys.length; i += 4) {
    let word = 0;
    for (let j = 0; j < 4 && i + j < keys.length; j += 1) {
      word |= (fields.get(keys[i + j]!)! & 3) << (j * 2);
    }
    w.uint32(word);
  }
}
