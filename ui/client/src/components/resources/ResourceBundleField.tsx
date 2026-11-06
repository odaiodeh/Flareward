import React, { useEffect, useState } from 'react';
import { captureResourceSnapshot, type ResourceInstance } from '@/api/resources';
import { useLatestRequest } from '@/hooks/use-latest-request';
import { isRecord } from '@/lib/json';
import type { SchemaField } from '@/components/schema/SchemaValue';
import SavedResourcePicker from './SavedResourcePicker';

/** Captures on explicit selection; redacted catalog configuration is never copied. */
export default function ResourceBundleField({ label, value, onChange, disabled, scope, teamId, onPendingChange }: SchemaField & {
  scope: string; teamId?: string; onPendingChange: (pending: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useLatestRequest();
  useEffect(() => () => onPendingChange(false), [onPendingChange]);
  const root = isRecord(value) && isRecord(value.root) ? value.root : null;
  const entries = isRecord(value) && Array.isArray(value.entries) ? value.entries : [];
  const selected = entries.find(entry => isRecord(entry) && isRecord(entry.resource) && isRecord(entry.resource.key) && entry.resource.key.rid === root?.rid && entry.resource.key.category === root?.category);
  const name = isRecord(selected) && isRecord(selected.resource) ? selected.resource.name : undefined;
  const capture = async (resource: ResourceInstance) => {
    if (!resource.source || busy) return;
    const signal = request(); setBusy(true); setError(''); onPendingChange(true);
    try {
      const bundle = await captureResourceSnapshot(resource.source, teamId, signal);
      if (!signal.aborted) onChange(bundle as unknown as SchemaField['value']);
    } catch {
      if (!signal.aborted) setError('Unable to capture this saved element. Refresh the library and select it again.');
    } finally {
      if (!signal.aborted) { setBusy(false); onPendingChange(false); }
    }
  };
  return <fieldset disabled={disabled || busy} className="space-y-3 rounded border p-3"><legend className="px-1 text-sm font-medium">{label}</legend>
    {root && <p className="text-sm">Captured: {typeof name === 'string' && name ? name : String(root.rid)} · {entries.length} configured element(s)</p>}
    <SavedResourcePicker scope={scope} teamId={teamId} disabled={disabled || busy} onSelect={resource => void capture(resource)} actionLabel={root ? 'Replace captured element' : 'Capture saved element'} />
    {busy && <p role="status">Capturing saved configuration and dependencies…</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    <p className="text-xs text-muted-foreground">Captures configuration and dependencies. Later resource edits require an explicit replacement; published revisions remain unchanged.</p>
  </fieldset>;
}
