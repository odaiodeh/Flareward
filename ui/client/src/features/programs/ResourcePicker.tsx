import React, { useState } from 'react';
import type { ResourceInstance } from '@/api/resources';
import type { ResourceSelection } from '@/api/programs';
import SavedResourcePicker from '@/components/resources/SavedResourcePicker';

/** Selection sends a source reference; display configuration never becomes execution data. */
export default function ResourcePicker({ scope, teamId, disabled, onSelect, category: fixedCategory, title = 'Add a saved element', actionLabel = 'Add element block' }: {
  scope: string; teamId?: string; disabled: boolean;
  category?: string; title?: string; actionLabel?: string;
  onSelect: (resource: ResourceInstance, adoption: ResourceSelection['adoption']) => void;
}) {
  const [chosenCategory, setCategory] = useState('operations');
  const category = fixedCategory ?? chosenCategory;
  const [replace, setReplace] = useState(false);
  return <section className="space-y-3"><h3 className="font-medium">{title}</h3>
    {!fixedCategory && <label className="block text-sm">Element category<select aria-label="Element category" className="block w-full rounded border bg-background p-2" value={category} disabled={disabled} onChange={event => setCategory(event.target.value)}>
      <option value="operations">Operations</option><option value="nodes">Workflow nodes</option>
    </select></label>}
    <label className="flex items-start gap-2 text-xs"><input type="checkbox" aria-label="Replace existing resource snapshots" disabled={disabled} checked={replace} onChange={event => setReplace(event.target.checked)} /><span>Replace existing saved configurations for all uses, including shared dependencies.</span></label>
    <SavedResourcePicker key={JSON.stringify([scope, teamId, category])} scope={scope} teamId={teamId} category={category} disabled={disabled} actionLabel={actionLabel} onSelect={resource => onSelect(resource, replace ? 'replace' : 'reject')} />
    <p className="text-xs text-muted-foreground">Save resolves dependencies on the server and freezes configuration. Later library changes do not change published runs.</p>
  </section>;
}
