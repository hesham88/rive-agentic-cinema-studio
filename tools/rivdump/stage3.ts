import { toggleRig } from '../../packages/rive-engine/src/core/riv/toggle';
import { decodeRiv, summarise } from '../../packages/rive-engine/src/core/riv/decode';
import { Prop, TypeKey } from '../../packages/rive-engine/src/core/riv/schema';
const typeNames = new Map(Object.entries(TypeKey).map(([n, k]) => [k as number, n]));
const propNames = new Map(Object.entries(Prop).map(([n, s]) => [s.key, n]));
const bytes = toggleRig();
console.log(`encoded ${bytes.length} bytes\n`);
console.log(summarise(decodeRiv(bytes), {
  type: (k) => typeNames.get(k), prop: (k) => propNames.get(k),
}));
