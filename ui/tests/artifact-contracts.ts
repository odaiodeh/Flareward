import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { ARTIFACT_PREVIEW_BYTES, readArtifactText } from '../client/src/api/artifacts';
import { artifactReferences } from '../client/src/lib/artifact-references';

export async function verifyArtifactContracts() {
  const data = new TextEncoder().encode('<script>display as text</script>\n');
  const reference = { artifact_id: 'a'.repeat(64), sha256: createHash('sha256').update(data).digest('hex'), size_bytes: data.length };
  assert.equal(artifactReferences([{ custom: [reference, reference] }]).references.length, 1);
  assert.equal(artifactReferences([{ ...reference, size_bytes: -1 }]).references.length, 0);
  assert.equal(artifactReferences([reference, { ...reference, sha256: 'b'.repeat(64) }]).references.length, 2);
  assert.equal(artifactReferences([Array.from({ length: 4096 }, () => ({}))]).truncated, true);
  const report = { artifact_id: 'b'.repeat(64), sha256: 'c'.repeat(64), size_bytes: 42 };
  const pendingSubject = {
    kind: 'engineering-review@1',
    candidate: { kind: 'blob-artifact@1', identity: reference },
    verification: { outcome: 'accepted', state: {
      plan: { subject: { kind: 'blob-artifact@1', identity: reference } },
      evidence: [{ reports: [{ content: report }] }],
    } },
  };
  const discovered = artifactReferences([pendingSubject]);
  assert.equal(discovered.truncated, false);
  assert.deepEqual(new Set(discovered.references.map(value => value.artifact_id)), new Set([reference.artifact_id, report.artifact_id]));
  const original = globalThis.fetch;
  let body: ReadableStream<Uint8Array>;
  let cancelled = false;
  try {
    globalThis.fetch = async () => {
      body = new ReadableStream({ start(controller) { controller.enqueue(data); controller.close(); } });
      return new Response(body);
    };
    assert.equal(await readArtifactText(reference), '<script>display as text</script>\n');
    assert.equal(body!.locked, false);
    await assert.rejects(readArtifactText({ ...reference, sha256: 'b'.repeat(64) }), /digest/);
    await assert.rejects(readArtifactText({ ...reference, size_bytes: data.length + 1 }), /size/);
    globalThis.fetch = async () => {
      body = new ReadableStream({ start(controller) { controller.enqueue(data); }, cancel() { cancelled = true; } });
      return new Response(body);
    };
    await assert.rejects(readArtifactText({ ...reference, size_bytes: 1 }), /exceeds/);
    assert.equal(cancelled, true);
    assert.equal(body!.locked, false);
    globalThis.fetch = async () => assert.fail('Oversized preview performed a request');
    await assert.rejects(readArtifactText({ ...reference, size_bytes: ARTIFACT_PREVIEW_BYTES + 1 }), /too large/);
  } finally { globalThis.fetch = original; }
}
