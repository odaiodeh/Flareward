import type { JsonObject, JsonValue } from '@shared/json';
import { isRecord } from '@/lib/json';

/** An unfinished numeric edit is not an absent setting or the previous valid number. */
export function parseSchemaNumber(text: string, schema: JsonObject): number | undefined {
  if (!text.trim()) return undefined;
  let value: unknown;
  try { value = JSON.parse(text); }
  catch { throw new Error('Enter a valid number.'); }
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Enter a finite number.');
  if (schema.type === 'integer' && !Number.isInteger(value)) throw new Error('Enter a whole number.');
  if (typeof schema.minimum === 'number' && value < schema.minimum || typeof schema.maximum === 'number' && value > schema.maximum
    || typeof schema.exclusiveMinimum === 'number' && value <= schema.exclusiveMinimum || typeof schema.exclusiveMaximum === 'number' && value >= schema.exclusiveMaximum) throw new Error('Enter a number within the allowed range.');
  return value;
}

/** Only local schema references are resolved; rendering never fetches remote URLs. */
export function resolveSchema(root: JsonObject, field: JsonValue, seen = new Set<string>()): JsonObject | null {
  if (!isRecord(field)) return null;
  let resolved = field as JsonObject;
  while (typeof resolved.$ref === 'string') {
    const ref = resolved.$ref;
    if (!ref.startsWith('#/') || seen.has(ref)) return null;
    seen.add(ref);
    let value: unknown = root;
    for (const part of ref.slice(2).split('/').map(value => value.replace(/~1/g, '/').replace(/~0/g, '~'))) {
      value = isRecord(value) && Object.hasOwn(value, part) ? value[part] : undefined;
    }
    if (!isRecord(value)) return null;
    resolved = { ...value, ...Object.fromEntries(Object.entries(resolved).filter(([key]) => key !== '$ref')) } as JsonObject;
  }
  if (Array.isArray(resolved.anyOf)) {
    const candidates = resolved.anyOf.filter(value => isRecord(value) && value.type !== 'null');
    if (candidates.length === 1) {
      const candidate = resolveSchema(root, candidates[0], seen);
      return candidate ? { ...candidate, ...Object.fromEntries(Object.entries(resolved).filter(([key]) => key !== 'anyOf')) } : null;
    }
  }
  return resolved;
}

/** Explicit defaults are copied; required scalar values remain unset for the user. */
export function initialSchemaInput(root: JsonObject): JsonValue {
  const schema = resolveSchema(root, root);
  if (schema && Object.hasOwn(schema, 'default')) return structuredClone(schema.default);
  if (schema?.type === 'array') return [];
  return schema?.type && schema.type !== 'object' ? null : {};
}

