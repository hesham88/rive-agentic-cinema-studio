/**
 * Dump a `.riv`'s object stream in a readable, diffable form.
 *
 * Used to compare files the Rive editor exported against files our encoder
 * produced — the editor is the reference implementation, so its structure is
 * the specification for ours.
 *
 *   npx tsx tools/rivdump/dump.ts <file.riv> [--head N]
 */

import { readFileSync } from 'node:fs';
import { decodeRiv, summarise } from '../../packages/rive-engine/src/core/riv/decode';
import {
  KNOWN_FIELDS,
  PROPERTY_NAMES,
  TYPE_NAMES,
} from '../../packages/rive-engine/src/core/riv/known-fields';

const [file, ...rest] = process.argv.slice(2);
if (!file) {
  console.error('usage: dump.ts <file.riv> [--head N]');
  process.exit(2);
}
const headIdx = rest.indexOf('--head');
const head = headIdx >= 0 ? Number(rest[headIdx + 1]) : Infinity;

const bytes = new Uint8Array(readFileSync(file));
try {
  const decoded = decodeRiv(bytes, KNOWN_FIELDS);
  const text = summarise(decoded, {
    type: (k) => TYPE_NAMES.get(k),
    prop: (k) => PROPERTY_NAMES.get(k),
  });
  const lines = text.split('\n');
  console.log(lines.slice(0, Number.isFinite(head) ? head : lines.length).join('\n'));
  if (lines.length > head) console.log(`... ${lines.length - head} more lines`);
} catch (e) {
  console.error(`decode failed: ${(e as Error).message}`);
  process.exit(1);
}
