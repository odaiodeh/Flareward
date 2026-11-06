import React, { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { listResourcePage, type ResourceInstance } from '@/api/resources';
import { Button } from '@/components/ui/button';

/** Catalog selection only: callers own capture or graph adoption semantics. */
export default function SavedResourcePicker({ scope, teamId, category, disabled, onSelect, actionLabel = 'Use saved element' }: {
  scope: string; teamId?: string; category?: string; disabled: boolean;
  onSelect: (resource: ResourceInstance) => void; actionLabel?: string;
}) {
  const [selected, setSelected] = useState('');
  const library = useInfiniteQuery({
    queryKey: ['saved-resource-library', scope, teamId, category], initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => listResourcePage({ category, offset: pageParam, limit: 50, teamId, signal }),
    getNextPageParam: page => page.resources.length && page.offset + page.resources.length < page.total ? page.offset + page.resources.length : undefined,
  });
  const resources = library.data?.pages.flatMap(page => page.resources) ?? [];
  const resource = resources.find(value => value.rid === selected);
  return <div className="space-y-3">
    <label className="block text-sm">Saved element<select aria-label="Saved element" className="block w-full rounded border bg-background p-2" value={selected} disabled={disabled || library.isPending} onChange={event => setSelected(event.target.value)}>
      <option value="">Select a configured element</option>{resources.map(value => <option key={value.rid} value={value.rid} disabled={!value.source}>{value.name} ({value.category} / {value.type}){value.source ? '' : ' / unavailable'}</option>)}
    </select></label>
    {library.error && <p role="alert" className="text-destructive">Unable to load saved elements. Refresh to retry.</p>}
    {library.hasNextPage && <Button type="button" variant="ghost" disabled={disabled || library.isFetchingNextPage} onClick={() => void library.fetchNextPage()}>Load more elements</Button>}
    <Button type="button" variant="ghost" disabled={disabled || library.isFetching} onClick={() => void library.refetch()}>Refresh elements</Button>
    <Button type="button" variant="outline" disabled={disabled || library.isFetching || library.isError || !resource?.source} onClick={() => { if (resource?.source) onSelect(resource); }}>{actionLabel}</Button>
  </div>;
}
