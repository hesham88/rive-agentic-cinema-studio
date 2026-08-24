/**
 * Encodes a document into `.riv` bytes.
 *
 * The body of a `.riv` is a FLAT stream of objects — there is no nesting in the
 * file at all. Structure comes from three things, and getting any of them wrong
 * produces a file that loads but renders nothing:
 *
 *   1. **Order.** `File::read` pushes each object onto an import stack; an
 *      object belongs to the most recently read Artboard. So every object must
 *      follow its artboard, and the Backboard must come first.
 *   2. **`parentId`** — an index into the artboard's own object list, not a
 *      global id and not a pointer.
 *   3. **Typed id references** — `animationId`, `stateToId`, `viewModelId` and
 *      friends, each indexing whatever list its owner keeps.
 *
 * The encoder therefore assigns indices as objects are appended, and callers
 * refer to earlier objects by the handle they got back.
 */

import { ByteWriter, FieldType, writeToc, type FieldTypeId } from './writer';
import { Prop, TypeKey, type PropertySpec } from './schema';

/** Format major version. Major versions are mutually unreadable. */
export const FORMAT_MAJOR = 7;
export const FORMAT_MINOR = 0;

export type PropValue = number | string | boolean | Uint8Array;

/** One object in the flat stream. */
export interface RivObject {
  typeKey: number;
  /** Ordered property writes. Order within an object does not matter to the reader. */
  props: Array<[PropertySpec, PropValue]>;
}

/**
 * A handle to an appended object.
 *
 * `index` is the artboard-relative index other objects use for `parentId`.
 * Handing back an opaque handle rather than a raw number is what stops the two
 * numbering schemes (stream position vs artboard index) being confused.
 */
export interface Handle {
  readonly index: number;
  readonly typeKey: number;
}

export class RivDocument {
  private objects: RivObject[] = [];
  /** Artboard-relative counter; resets when a new artboard starts. */
  private indexInArtboard = 0;

  /** Append an object and return its artboard-relative handle. */
  add(typeKey: number, props: Array<[PropertySpec, PropValue]> = []): Handle {
    // The artboard itself is index 0 of its own scope; its children follow.
    if (typeKey === TypeKey.artboard) {
      this.indexInArtboard = 0;
    }
    const handle: Handle = { index: this.indexInArtboard, typeKey };
    this.objects.push({ typeKey, props });
    this.indexInArtboard += 1;
    return handle;
  }

  /** Every property key used, with its backing type — this becomes the ToC. */
  private collectFields(): Map<number, FieldTypeId> {
    const fields = new Map<number, FieldTypeId>();
    for (const o of this.objects) {
      for (const [spec] of o.props) {
        const existing = fields.get(spec.key);
        if (existing !== undefined && existing !== spec.field) {
          throw new Error(
            `property key ${spec.key} declared as both field type ${existing} and ${spec.field}`,
          );
        }
        fields.set(spec.key, spec.field);
      }
    }
    return fields;
  }

  private static writeValue(w: ByteWriter, field: FieldTypeId, value: PropValue): void {
    switch (field) {
      case FieldType.uint:
        if (typeof value === 'boolean') {
          // Bools are one raw byte. They share the uint field id, which is only
          // safe because 0/1 encode identically either way.
          w.bool(value);
        } else if (typeof value === 'number') {
          w.varUint(value);
        } else {
          throw new TypeError(`uint property needs a number or boolean, got ${typeof value}`);
        }
        return;
      case FieldType.string:
        if (value instanceof Uint8Array) w.blob(value);
        else if (typeof value === 'string') w.string(value);
        else throw new TypeError(`string property needs a string or bytes, got ${typeof value}`);
        return;
      case FieldType.double:
        if (typeof value !== 'number') throw new TypeError('double property needs a number');
        w.float(value);
        return;
      case FieldType.color:
        if (typeof value !== 'number') throw new TypeError('color property needs a packed uint32');
        w.uint32(value);
        return;
      default: {
        const never: never = field;
        throw new Error(`unhandled field type ${never}`);
      }
    }
  }

  encode({ fileId = 0 }: { fileId?: number } = {}): Uint8Array {
    if (this.objects.length === 0) {
      throw new Error('refusing to encode an empty document');
    }
    if (this.objects[0]!.typeKey !== TypeKey.backboard) {
      throw new Error('the first object must be the Backboard');
    }

    const w = new ByteWriter(4096);

    // Header
    w.bytes(new TextEncoder().encode('RIVE'));
    w.varUint(FORMAT_MAJOR);
    w.varUint(FORMAT_MINOR);
    w.varUint(fileId);

    // Table of contents. Every key we emit must appear here: a property the
    // runtime cannot resolve — from its own registry or from this table — is a
    // hard failure that rejects the whole file, not a skipped property.
    writeToc(w, this.collectFields());

    // Body
    for (const o of this.objects) {
      w.varUint(o.typeKey);
      for (const [spec, value] of o.props) {
        w.varUint(spec.key);
        RivDocument.writeValue(w, spec.field, value);
      }
      w.varUint(0);
    }

    return w.toUint8Array();
  }
}

/** Convenience: the properties every named child of an artboard carries. */
export function named(name: string, parent: Handle): Array<[PropertySpec, PropValue]> {
  return [
    [Prop.name, name],
    [Prop.parentId, parent.index],
  ];
}
