/**
 * Reads a `.riv` back into its object stream.
 *
 * Two reasons this exists rather than just an encoder:
 *
 *   1. **The editor is the reference implementation.** Reverse-engineering how
 *      Rive structures a state machine from the C++ importers is guesswork;
 *      decoding a file the editor exported is evidence. Diffing our output
 *      against theirs is how the encoder gets verified.
 *   2. A decoder makes the encoder testable without a browser. `encode → decode`
 *      round-trips catch key and type mistakes in milliseconds, where the WASM
 *      runtime only ever says yes or no.
 *
 * It is deliberately schema-agnostic: it uses the file's own table of contents
 * to decide how to read each value, exactly as the runtime does for properties
 * it does not recognise. That means it can read files containing objects this
 * library knows nothing about.
 */

import { FieldType, type FieldTypeId } from './writer';

export interface DecodedProperty {
  key: number;
  field: FieldTypeId;
  value: number | string | boolean | Uint8Array;
}

export interface DecodedObject {
  typeKey: number;
  props: DecodedProperty[];
}

export interface DecodedFile {
  majorVersion: number;
  minorVersion: number;
  fileId: number;
  /** Property key -> backing field type, from the header. */
  toc: Map<number, FieldTypeId>;
  objects: DecodedObject[];
}

class Reader {
  private pos = 0;
  constructor(private readonly bytes: Uint8Array) {}

  get done(): boolean {
    return this.pos >= this.bytes.length;
  }

  get offset(): number {
    return this.pos;
  }

  byte(): number {
    if (this.pos >= this.bytes.length) throw new RangeError('read past end of file');
    return this.bytes[this.pos++]!;
  }

  varUint(): number {
    let result = 0;
    let shift = 1;
    for (;;) {
      const b = this.byte();
      result += (b & 0x7f) * shift;
      if ((b & 0x80) === 0) return result;
      shift *= 128;
      if (shift > 2 ** 56) throw new RangeError('varint too long');
    }
  }

  uint32(): number {
    const a = this.byte();
    const b = this.byte();
    const c = this.byte();
    const d = this.byte();
    return ((a | (b << 8) | (c << 16) | (d << 24)) >>> 0);
  }

  float(): number {
    const view = new DataView(this.bytes.buffer, this.bytes.byteOffset + this.pos, 4);
    this.pos += 4;
    return view.getFloat32(0, true);
  }

  string(): string {
    const len = this.varUint();
    const slice = this.bytes.subarray(this.pos, this.pos + len);
    this.pos += len;
    return new TextDecoder().decode(slice);
  }

  magic(): string {
    return String.fromCharCode(this.byte(), this.byte(), this.byte(), this.byte());
  }
}

/**
 * Decode a `.riv`.
 *
 * `knownFields` supplies backing types for property keys the file's own ToC
 * omits. That is not a nicety: the runtime resolves a key from its compiled-in
 * registry FIRST and only consults the ToC as a fallback, so a real editor
 * export legitimately leaves well-known keys out of the table. Without the same
 * knowledge a decoder desynchronises the moment it meets one.
 */
export function decodeRiv(
  bytes: Uint8Array,
  knownFields?: ReadonlyMap<number, FieldTypeId>,
): DecodedFile {
  const r = new Reader(bytes);

  const magic = r.magic();
  if (magic !== 'RIVE') {
    throw new Error(`not a Rive file: expected "RIVE", got ${JSON.stringify(magic)}`);
  }

  const majorVersion = r.varUint();
  const minorVersion = r.varUint();
  const fileId = r.varUint();

  const keys: number[] = [];
  for (let k = r.varUint(); k !== 0; k = r.varUint()) keys.push(k);

  const toc = new Map<number, FieldTypeId>();
  let word = 0;
  let bit = 8;
  for (const key of keys) {
    if (bit === 8) {
      word = r.uint32();
      bit = 0;
    }
    toc.set(key, ((word >> bit) & 3) as FieldTypeId);
    bit += 2;
  }

  const fieldFor = (key: number): FieldTypeId => {
    const fromToc = toc.get(key);
    if (fromToc !== undefined) return fromToc;
    const known = knownFields?.get(key);
    if (known !== undefined) return known;
    throw new Error(
      `property key ${key} at byte ${r.offset} is in neither the file's ToC nor the ` +
        `supplied schema, so its length is unknowable and the stream cannot continue`,
    );
  };

  const objects: DecodedObject[] = [];
  while (!r.done) {
    const typeKey = r.varUint();
    const props: DecodedProperty[] = [];
    for (;;) {
      const key = r.varUint();
      if (key === 0) break;
      const field = fieldFor(key);
      let value: DecodedProperty['value'];
      switch (field) {
        case FieldType.uint:
          value = r.varUint();
          break;
        case FieldType.string:
          value = r.string();
          break;
        case FieldType.double:
          value = r.float();
          break;
        case FieldType.color:
          value = r.uint32();
          break;
        default:
          throw new Error(`unhandled field type ${field}`);
      }
      props.push({ key, field, value });
    }
    objects.push({ typeKey, props });
  }

  return { majorVersion, minorVersion, fileId, toc, objects };
}

/** A compact, diffable rendering of a decoded file. */
export function summarise(
  file: DecodedFile,
  names?: {
    type?: (k: number) => string | undefined;
    prop?: (k: number) => string | undefined;
  },
): string {
  const lines: string[] = [
    `RIVE ${file.majorVersion}.${file.minorVersion}  fileId=${file.fileId}  ` +
      `toc=${file.toc.size} keys  objects=${file.objects.length}`,
  ];
  for (const [i, o] of file.objects.entries()) {
    const tn = names?.type?.(o.typeKey);
    lines.push(`[${i}] type ${o.typeKey}${tn ? ` (${tn})` : ''}`);
    for (const p of o.props) {
      const pn = names?.prop?.(p.key);
      const v =
        typeof p.value === 'number' && p.field === FieldType.color
          ? `#${(p.value >>> 0).toString(16).padStart(8, '0')}`
          : typeof p.value === 'number'
            ? Number(p.value.toFixed(4))
            : JSON.stringify(p.value);
      lines.push(`      ${p.key}${pn ? ` ${pn}` : ''} = ${v}`);
    }
  }
  return lines.join('\n');
}
