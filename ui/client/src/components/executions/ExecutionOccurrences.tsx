import React from 'react';
import { Link } from 'wouter';
import { useInfiniteQuery } from '@tanstack/react-query';
import { inspectExecutionOccurrences, type CallOccurrence } from '@/api/programs';
import { Button } from '@/components/ui/button';

/** Displays observed work; coordinator topology and scheduling remain outside the UI. */
export default function ExecutionOccurrences({ id, scope, teamId, active }: {
  id: string; scope: string; teamId?: string; active: boolean;
}) {
  const query = useInfiniteQuery({
    queryKey: ['execution-occurrences', scope, id],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam, signal }) => inspectExecutionOccurrences(id, pageParam, teamId, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    refetchInterval: active ? 1500 : false, retry: false,
  });
  const pages = query.data?.pages ?? [];
  const calls = new Map<number, CallOccurrence>();
  // A later snapshot wins when live pagination overlaps an earlier page.
  for (const page of pages.toSorted((a, b) => a.revision - b.revision)) {
    for (const call of page.occurrences) calls.set(call.ordinal, call);
  }
  const rows = [...calls.values()].sort((a, b) => b.ordinal - a.ordinal);
  return <section aria-label="Observed calls" className="space-y-3">
    <div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">Observed calls</h2><p className="text-xs text-muted-foreground">Last observed status for each call and graph attempt.</p></div>
      <Button variant="ghost" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh calls</Button></div>
    {query.isPending && <p role="status">Loading observed calls…</p>}
    {query.isError && <p role="alert">Call observation is unavailable. {rows.length > 0 ? 'The last observation is shown.' : 'Refresh to try again.'}</p>}
    {pages[0]?.truncated && <p role="status" className="text-sm">Earlier calls are outside this snapshot’s retention window. This is a partial history.</p>}
    {rows.length > 0 && <div className="overflow-x-auto rounded border"><table className="w-full text-left text-sm"><caption className="sr-only">Observed calls and attempts</caption>
      <thead className="bg-muted"><tr>{['Call', 'Kind', 'Step / attempt', 'Status', 'Execution'].map(label => <th key={label} scope="col" className="p-3 font-medium">{label}</th>)}</tr></thead>
      <tbody>{rows.map(call => <tr key={call.ordinal} className="border-t"><td className="p-3"><span className="text-xs text-muted-foreground">#{call.ordinal} </span>{call.call_site}</td><td className="p-3">{call.kind}</td>
        <td className="p-3">{call.graph_step === null ? '—' : call.graph_step} / {call.attempt}</td><td className="p-3">{call.status}</td><td className="p-3">{call.child_execution_id ? <Link className="underline" href={`/executions/${encodeURIComponent(call.child_execution_id)}`}>Inspect child</Link> : '—'}</td></tr>)}</tbody>
    </table></div>}
    {!query.isPending && !query.isError && rows.length === 0 && <p className="text-sm text-muted-foreground">No calls observed yet.</p>}
    {query.hasNextPage && <Button variant="outline" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>Load earlier calls</Button>}
  </section>;
}
