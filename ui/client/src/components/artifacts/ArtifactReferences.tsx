import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { JsonValue } from '@shared/json';
import { ARTIFACT_PREVIEW_BYTES, artifactContentUrl, inspectArtifact, readArtifactText, type ArtifactReference } from '@/api/artifacts';
import { artifactReferences } from '@/lib/artifact-references';
import { useLatestRequest } from '@/hooks/use-latest-request';
import { Button } from '@/components/ui/button';

/** Same reference inspector is used for execution outcomes and the exact reviewed subject. */
export default function ArtifactReferences({ values, scope, teamId }: { values: JsonValue[]; scope: string; teamId?: string }) {
  const found = artifactReferences(values);
  if (!found.references.length && !found.truncated) return null;
  return <section aria-label="Referenced artifacts" className="space-y-3"><h3 className="font-semibold">Artifacts and reports</h3>
    {found.references.map(reference => <ArtifactCard key={JSON.stringify([scope, reference])} reference={reference} scope={scope} teamId={teamId} />)}
    {found.truncated && <p className="text-sm">Reference discovery was limited. Additional references may remain in the structured data.</p>}
  </section>;
}

function ArtifactCard({ reference, scope, teamId }: { reference: ArtifactReference; scope: string; teamId?: string }) {
  const [expanded, setExpanded] = useState(false);
  return <div className="space-y-3 rounded border p-3"><p className="break-all text-xs">{reference.artifact_id}</p>
    <Button type="button" variant="outline" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Close artifact' : 'Inspect artifact'}</Button>
    {expanded && <ArtifactDetail reference={reference} scope={scope} teamId={teamId} />}
  </div>;
}

function ArtifactDetail({ reference, scope, teamId }: { reference: ArtifactReference; scope: string; teamId?: string }) {
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useLatestRequest();
  const metadata = useQuery({
    queryKey: ['artifact', scope, reference.artifact_id, reference.sha256, reference.size_bytes],
    queryFn: ({ signal }) => inspectArtifact(reference, teamId, signal), retry: false,
  });
  const preview = async () => {
    if (busy) return;
    const signal = request(); setBusy(true); setError(''); setText(null);
    try {
      const value = await readArtifactText(reference, teamId, signal);
      if (!signal.aborted) setText(value);
    } catch { if (!signal.aborted) setError('Text preview is unavailable or content verification failed.'); }
    finally { if (!signal.aborted) setBusy(false); }
  };
  return <div className="space-y-3 text-sm">
    {metadata.isPending && <p role="status">Loading artifact metadata…</p>}
    {metadata.isError && <p role="alert">Artifact metadata is unavailable or does not match the reference.</p>}
    {metadata.data && !metadata.isError && <><p>{metadata.data.name} · {metadata.data.media_type} · {reference.size_bytes} bytes</p>
      <a className="inline-block underline" href={artifactContentUrl(reference, teamId)} download>Download artifact</a>
      {reference.size_bytes <= ARTIFACT_PREVIEW_BYTES && <Button type="button" variant="outline" disabled={busy} onClick={() => void preview()}>{busy ? 'Loading preview…' : 'Preview verified text'}</Button>}
      {error && <p role="alert">{error}</p>}
      {text !== null && <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-3">{text}</pre>}
    </>}
  </div>;
}
