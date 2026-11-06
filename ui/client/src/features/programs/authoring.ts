import type { JsonObject, JsonValue } from '@shared/json';
import type { ProgramDescriptor, ProgramSummary, ProgramTarget } from '@/api/programs';
import { isRecord } from '@/lib/json';
import { resolveSchema } from '@/components/schema/schema';

export function programTargetLabel(target: ProgramTarget, programs: ProgramSummary[]): string {
  if ('program_id' in target) {
    const name = programs.find(program => program.program_id === target.program_id)?.name ?? target.program_id;
    return `${name} / r${target.revision}`;
  }
  return target.implementation.kind === 'application' ? `Inline ${target.implementation.implementation}` : 'Inline workflow';
}

export function configurationDefaults(descriptor: ProgramDescriptor): JsonObject {
  const root = descriptor.configuration_schema;
  if (!isRecord(root.properties)) return {};
  return Object.fromEntries(Object.entries(root.properties).flatMap(([name, field]) => {
    const schema = resolveSchema(root, field as JsonValue);
    return schema && Object.hasOwn(schema, 'default') ? [[name, structuredClone(schema.default)]] : [];
  }));
}

export function programError(value: unknown): string {
  if (isRecord(value) && isRecord(value.response) && isRecord(value.response.data) && typeof value.response.data.detail === 'string') return value.response.data.detail;
  return value instanceof Error ? value.message : 'The request could not be confirmed. Reload before changing the saved draft.';
}
