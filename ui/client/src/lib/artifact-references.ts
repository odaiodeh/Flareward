import type { JsonValue } from '@shared/json';
import type { ArtifactReference } from '@/api/artifacts';
import { isRecord } from './json';

/** Recognize the generic blob-reference contract, never application-specific result paths. */
export function artifactReferences(values: JsonValue[]): { references: ArtifactReference[]; truncated: boolean } {
  const pending = values.map(value => ({ value, depth: 0 }));
  const references = new Map<string, ArtifactReference>();
  let remaining = 2048;
  let truncated = false;
  while (pending.length && remaining-- > 0 && references.size < 32) {
    const { value, depth } = pending.pop()!;
    if (isRecord(value) && Object.keys(value).length === 3 && typeof value.artifact_id === 'string' && /^[a-f0-9]{64}$/.test(value.artifact_id) && typeof value.sha256 === 'string' && /^[a-f0-9]{64}$/.test(value.sha256) && typeof value.size_bytes === 'number' && Number.isSafeInteger(value.size_bytes) && value.size_bytes >= 0) {
      const reference = { artifact_id: value.artifact_id, sha256: value.sha256, size_bytes: value.size_bytes };
      references.set(JSON.stringify(reference), reference);
    } else if (Array.isArray(value) || isRecord(value)) {
      if (depth >= 16) { truncated = true; continue; }
      const children = Array.isArray(value) ? value : Object.values(value) as JsonValue[];
      const capacity = Math.max(0, remaining - pending.length);
      if (children.length > capacity) truncated = true;
      pending.push(...children.slice(0, capacity).map(child => ({ value: child, depth: depth + 1 })));
    }
  }
  return { references: [...references.values()], truncated: truncated || pending.length > 0 };
}
