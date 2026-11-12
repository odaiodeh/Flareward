import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'wouter';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import type { JsonValue } from '@shared/json';
import { getProgramRevision, startProgram, type ProgramRef, type ProgramRevision, type StartProgram, type WorkflowAccess } from '@/api/programs';
import SchemaValue from '@/components/schema/SchemaValue';
import { initialSchemaInput } from '@/components/schema/schema';
import JsonField from '@/components/schema/JsonField';
import { Button } from '@/components/ui/button';
import { useLatestRequest } from '@/hooks/use-latest-request';
import { executionPath } from './ExecutionWorkbench';
import WorkflowAccessFields from './WorkflowAccessFields';

/** Invocation reads the selected immutable revision, independently of editable drafts. */
export default function ProgramInvocation({ program, scope, teamId, onBusyChange }: {
  program: ProgramRef; scope: string; teamId?: string; onBusyChange: (busy: boolean) => void;
}) {
  const revision = useQuery({
    queryKey: ['invocation-contract', scope, program.program_id, program.revision],
    queryFn: ({ signal }) => getProgramRevision(program, teamId, signal),
    refetchOnWindowFocus: false, refetchOnReconnect: false, retry: false,
  });
  return <section aria-label="Program invocation" className="space-y-3 rounded border p-4"><h2 className="font-semibold">Run revision {program.revision}</h2>
    {revision.isPending && <p role="status">Loading published input contract…</p>}
    {revision.isError ? <div role="alert">Published input contract is unavailable. <Button variant="outline" onClick={() => void revision.refetch()}>Retry loading inputs</Button></div> : revision.data && <InvocationInputs key={revision.data.content_digest} revision={revision.data} scope={scope} teamId={teamId} onBusyChange={onBusyChange} />}
  </section>;
}

function InvocationInputs({ revision, scope, teamId, onBusyChange }: {
  revision: ProgramRevision; scope: string; teamId?: string; onBusyChange: (busy: boolean) => void;
}) {
  const schema = revision.interface.configured?.input_schema ?? revision.interface.input_schema;
  const [inputs, setInputs] = useState<JsonValue>(() => initialSchemaInput(schema));
  const [advanced, setAdvanced] = useState(false);
  const [intent, setIntent] = useState<StartProgram | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [rejected, setRejected] = useState(false);
  const [requirements, setRequirements] = useState<WorkflowAccess[]>([]);
  const [approved, setApproved] = useState(false);
  const fields = useRef<HTMLFieldSetElement>(null);
  const active = useRef(false);
  const request = useLatestRequest();
  const [, navigate] = useLocation();
  useEffect(() => () => onBusyChange(false), [onBusyChange]);
  const submit = async () => {
    if (active.current || requirements.length > 0 && !approved) return;
    const signal = request(); active.current = true; setBusy(true); onBusyChange(true); setError('');
    const submission = intent && !rejected ? intent : { execution_id: intent?.execution_id ?? crypto.randomUUID(), program: { program_id: revision.definition.program_id, revision: revision.revision }, inputs: structuredClone(inputs), workflow_access: structuredClone(requirements) };
    setRejected(false);
    setIntent(submission);
    try {
      const accepted = await startProgram(submission, teamId, signal);
      if (!signal.aborted) navigate(executionPath(accepted.execution_id));
    } catch (failure) {
      if (!signal.aborted) {
        const invalid = axios.isAxiosError(failure) && failure.response?.status === 422;
        setRejected(invalid);
        setError(invalid ? 'The request was rejected. Correct the inputs and retry with the same execution identity.' : 'The execution request was not confirmed. Retry preserves its identity and inputs, or inspect the execution before submitting other work.');
      }
    } finally {
      if (!signal.aborted) { active.current = false; setBusy(false); onBusyChange(false); }
    }
  };
  return <form className="space-y-4" onSubmit={event => { event.preventDefault(); void submit(); }}>
    <fieldset ref={fields} disabled={busy || !!intent && !rejected} className="space-y-3">
      <Button type="button" variant="ghost" onClick={() => {
        // Changing views must not silently discard an unparsed JSON or numeric edit.
        if (Array.from(fields.current?.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea') ?? []).every(input => !(input.validity.customError || input.validity.badInput) || input.reportValidity())) setAdvanced(value => !value);
      }}>{advanced ? 'Use structured inputs' : 'Use JSON inputs'}</Button>
      {advanced ? <JsonField label="Program inputs (JSON)" value={inputs} onChange={setInputs} disabled={busy || !!intent && !rejected} /> : <SchemaValue schema={schema} label="Program inputs" value={inputs} onChange={value => setInputs(value ?? null)} disabled={busy || !!intent && !rejected} />}
      <WorkflowAccessFields scope={scope} teamId={teamId} value={requirements} disabled={busy || !!intent && !rejected} onChange={next => { setRequirements(next); setApproved(false); }} />
      {requirements.length > 0 && <label className="flex items-start gap-2 text-sm"><input type="checkbox" aria-label="Approve workflow permissions" required checked={approved} onChange={event => setApproved(event.target.checked)} />I approve these permissions for this execution and the selected lease durations.</label>}
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {intent && !busy && <Link className="block text-sm underline" href={executionPath(intent.execution_id)}>Inspect submitted execution</Link>}
    <Button disabled={busy} type="submit">{busy ? 'Submitting…' : rejected ? 'Retry corrected execution' : intent ? 'Retry same execution' : 'Run program'}</Button>
  </form>;
}
