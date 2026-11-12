import React, { useState } from 'react';
import { Link } from 'wouter';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { cancelProgramExecution, inspectProgramExecution, listProgramExecutionChildren, type ProgramExecution } from '@/api/programs';
import ExecutionOccurrences from './ExecutionOccurrences';
import ExecutionReviews from '@/components/reviews/ExecutionReviews';
import ArtifactReferences from '@/components/artifacts/ArtifactReferences';
import { Button } from '@/components/ui/button';
import { useLatestRequest } from '@/hooks/use-latest-request';

export const executionPath = (id: string) => `/executions/${encodeURIComponent(id)}`;
export const isExecutionTerminal = (value: ProgramExecution) => ['completed', 'failed', 'cancelled'].includes(value.phase);

/** The same persisted execution is inspected from Programs, Sessions and review links. */
export default function ExecutionWorkbench({ id, scope, teamId, human }: {
  id: string; scope: string; teamId?: string; human: string;
}) {
  const [cancelling, setCancelling] = useState(false);
  const [commandError, setCommandError] = useState('');
  const request = useLatestRequest();
  const cache = useQueryClient();
  const observation = useQuery({
    queryKey: ['execution', scope, id], queryFn: ({ signal }) => inspectProgramExecution(id, teamId, signal),
    refetchInterval: query => query.state.data && isExecutionTerminal(query.state.data) ? false : 1500,
    retry: false,
  });
  const record = observation.data;
  const children = useQuery({
    queryKey: ['execution-children', scope, id], enabled: !!record,
    queryFn: ({ signal }) => listProgramExecutionChildren(id, teamId, signal),
    refetchInterval: query => record && isExecutionTerminal(record) && query.state.data ? false : 1500,
    retry: false,
  });
  const cancel = async () => {
    if (cancelling) return;
    const signal = request(); setCancelling(true); setCommandError('');
    try {
      await cancelProgramExecution(id, teamId, signal);
      if (!signal.aborted) await cache.invalidateQueries({ queryKey: ['execution', scope, id] });
    } catch {
      if (!signal.aborted) setCommandError('Cancellation could not be confirmed. Refresh the observation before retrying.');
    } finally { if (!signal.aborted) setCancelling(false); }
  };
  return <section aria-label="Execution workbench" className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-semibold">Execution</h1><Button variant="outline" onClick={() => {
      void observation.refetch(); void children.refetch();
    }}>Refresh observation</Button></div>
    <p className="break-all text-xs text-muted-foreground">{id}</p>
    {observation.isPending && <p role="status">Loading execution…</p>}
    {observation.isError && <p role="alert">Execution observation is unavailable. {record ? 'The last observed state is shown below.' : 'Check the execution identity and selected workspace, then retry.'}</p>}
    {record && <>
      <div className="flex flex-wrap gap-3 text-sm" role="status"><span>{observation.isError ? 'Last observed phase' : 'Execution phase'}: {record.phase}</span><span>Submission: {record.submission}</span>{record.cancel_requested && <span>Cancellation requested</span>}</div>
      <p className="text-sm">Program: {record.program.program_id} / revision {record.program.revision}{record.body_path.length ? ` / ${record.body_path.join(' / ')}` : ''}</p>
      {record.workflow_access_approval && <details><summary className="font-medium">Approved workflow permissions</summary><p className="text-sm">Approved by {record.workflow_access_approval.approved_by.id} for root {record.workflow_access_approval.root_execution_id}</p><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-3 text-sm">{JSON.stringify(record.workflow_access_approval.requirements, null, 2)}</pre></details>}
      <nav aria-label="Execution relationships" className="flex flex-wrap gap-3 text-sm">
        {record.parent_execution_id && <Link className="underline" href={executionPath(record.parent_execution_id)}>Parent execution</Link>}
        {record.context.root_execution_id !== id && <Link className="underline" href={executionPath(record.context.root_execution_id)}>Root execution</Link>}
        {record.session_id && <Link className="underline" href={`/agentic-chats/${encodeURIComponent(record.session_id)}`}>Session conversation</Link>}
      </nav>
      {!isExecutionTerminal(record) && <Button variant="outline" disabled={cancelling || observation.isError || record.cancel_requested} onClick={() => void cancel()}>{cancelling ? 'Requesting cancellation…' : 'Request cancellation'}</Button>}
      {commandError && <p role="alert">{commandError}</p>}
      <section aria-label="Nested executions" className="space-y-3"><h2 className="font-semibold">Nested Programs</h2>
        {children.isPending && <p role="status">Loading nested executions…</p>}
        {children.isError && <p role="alert">Nested execution observation is unavailable.</p>}
        {children.data?.map(child => <Link key={child.execution_id} href={executionPath(child.execution_id)} className="block rounded border p-3 text-sm"><span className="font-medium">{child.program.program_id} / revision {child.program.revision}{child.body_path.length ? ` / ${child.body_path.join(' / ')}` : ''}</span><span className="ml-3">{child.phase}</span><span className="mt-1 block break-all text-xs text-muted-foreground">{child.execution_id}</span></Link>)}
        {children.data?.length === 0 && !children.isError && <p className="text-sm text-muted-foreground">No child executions observed.</p>}
      </section>
      <ExecutionOccurrences id={id} scope={scope} teamId={teamId} active={!isExecutionTerminal(record)} />
      <ExecutionReviews key={record.context.root_execution_id} root={record.context.root_execution_id} scope={scope} teamId={teamId} human={human} />
      <ArtifactReferences values={[record.inputs, record.result]} scope={scope} teamId={teamId} />
      <details open><summary className="font-semibold">Inputs</summary><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-3 text-sm">{JSON.stringify(record.inputs, null, 2)}</pre></details>
      {record.failure && <section aria-label="Execution failure"><h2 className="font-semibold">Failure</h2><p>{record.failure.kind}: {record.failure.message}</p></section>}
      {isExecutionTerminal(record) && !record.failure && <section aria-label="Execution result"><h2 className="font-semibold">Result</h2><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-3 text-sm">{JSON.stringify(record.result, null, 2)}</pre></section>}
    </>}
  </section>;
}
