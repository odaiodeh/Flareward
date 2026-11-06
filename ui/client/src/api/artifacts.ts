import api from '@/http/axiosAgentConfig';

export interface ArtifactReference { artifact_id: string; sha256: string; size_bytes: number }
export interface ArtifactRecord {
  reference: ArtifactReference; owner: { type: 'user' | 'team'; id: string; display_name: string };
  namespace: string; name: string; media_type: string; inputs: ArtifactReference[]; created_at: string;
}
export const ARTIFACT_PREVIEW_BYTES = 262144;

export async function inspectArtifact(reference: ArtifactReference, teamId?: string, signal?: AbortSignal): Promise<ArtifactRecord> {
  const record = (await api.get<ArtifactRecord>(`/artifacts/${encodeURIComponent(reference.artifact_id)}`, { params: { teamId }, signal })).data;
  if (record.reference.artifact_id !== reference.artifact_id || record.reference.sha256 !== reference.sha256 || record.reference.size_bytes !== reference.size_bytes) throw new Error('Artifact reference does not match stored content.');
  return record;
}

export function artifactContentUrl(reference: ArtifactReference, teamId?: string): string {
  return api.getUri({ url: `/artifacts/${encodeURIComponent(reference.artifact_id)}/content`, params: { teamId } });
}

/** Bound the stream and verify the exact referenced bytes before decoding display text. */
export async function readArtifactText(reference: ArtifactReference, teamId?: string, signal?: AbortSignal): Promise<string> {
  if (!Number.isSafeInteger(reference.size_bytes) || reference.size_bytes < 0 || reference.size_bytes > ARTIFACT_PREVIEW_BYTES) throw new Error('Artifact is too large for text preview.');
  const response = await fetch(artifactContentUrl(reference, teamId), { credentials: 'include', signal });
  if (!response.ok || !response.body) {
    await response.body?.cancel().catch(() => undefined);
    throw new Error('Artifact content is unavailable.');
  }
  const reader = response.body.getReader();
  const bytes = new Uint8Array(reference.size_bytes);
  let size = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > bytes.byteLength) throw new Error('Artifact content exceeds its referenced size.');
      bytes.set(chunk.value, size - chunk.value.byteLength);
    }
    if (size !== bytes.byteLength) throw new Error('Artifact content size does not match.');
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
    if (hash !== reference.sha256) throw new Error('Artifact content digest does not match.');
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } finally {
    try { await reader.cancel().catch(() => undefined); } finally { reader.releaseLock(); }
  }
}
