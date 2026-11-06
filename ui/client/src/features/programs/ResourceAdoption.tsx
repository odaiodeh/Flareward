import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getResourceSnapshotSource } from '@/api/resources';
import type { ResourceSelection } from '@/api/programs';
import type { ResourceKey } from '@/types/workspace';
import { Button } from '@/components/ui/button';
import { programError } from './authoring';

export default function ResourceAdoption({ resource, scope, teamId, disabled, onSelect }: {
  resource: ResourceKey; scope: string; teamId?: string; disabled: boolean;
  onSelect: (selection: ResourceSelection) => void;
}) {
  const current = useQuery({
    queryKey: ['program-resource-source', scope, resource.category, resource.rid],
    queryFn: ({ signal }) => getResourceSnapshotSource(resource.rid, teamId, signal),
  });
  return <details className="space-y-2 text-sm"><summary>Update saved configuration</summary>
    <p className="text-xs text-muted-foreground">Explicitly adopt the current saved configuration and dependencies for every use of this resource in this draft. Published revisions remain unchanged.</p>
    {current.error && <p role="alert" className="text-destructive">{programError(current.error)}</p>}
    <Button type="button" variant="ghost" disabled={disabled || current.isFetching} onClick={() => void current.refetch()}>Refresh source</Button>
    <Button type="button" variant="outline" disabled={disabled || current.isFetching || !current.data?.source} onClick={() => {
      if (current.data?.source) onSelect({ source: current.data.source, adoption: 'replace' });
    }}>Adopt current configuration for all uses</Button>
  </details>;
}
