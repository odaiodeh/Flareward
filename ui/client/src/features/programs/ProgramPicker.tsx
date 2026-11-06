import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProgramRevision, type ProgramRef, type ProgramSummary } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { programError } from './authoring';
import { useProgramRevisions } from './queries';

/** Choosing a program never silently follows its latest revision. */
export default function ProgramPicker({ value, onChange, programs, teamId, scope, disabled, label }: {
  value?: ProgramRef; onChange: (value: ProgramRef) => void; programs: ProgramSummary[];
  teamId?: string; scope: string; disabled?: boolean; label: string;
}) {
  const [selected, setSelected] = React.useState(value?.program_id ?? '');
  const revisions = useProgramRevisions(selected, scope, teamId);
  const pinned = useQuery({
    queryKey: ['program-revision', scope, value?.program_id, value?.revision], enabled: !!value,
    queryFn: ({ signal }) => getProgramRevision(value!, teamId, signal),
  });
  const selectedPin = value?.program_id === selected ? String(value.revision) : '';
  return <div className="space-y-2">
    <label className="block text-sm">{label}<select aria-label={label} className="mt-1 block w-full rounded border bg-background p-2" value={selected} disabled={disabled} onChange={event => setSelected(event.target.value)}>
      <option value="">Select a saved program</option>
      {selected && !programs.some(program => program.program_id === selected) && <option value={selected}>{pinned.data?.definition.name ?? selected}</option>}
      {programs.map(program => <option key={program.program_id} value={program.program_id}>{program.name}</option>)}
    </select></label>
    {selected && <label className="block text-sm">Published revision<select aria-label={`${label} revision`} className="mt-1 block w-full rounded border bg-background p-2" value={selectedPin} disabled={disabled || revisions.isPending} onChange={event => {
      if (event.target.value) onChange({ program_id: selected, revision: Number(event.target.value) });
    }}><option value="">Select a published revision</option>
      {selectedPin && !revisions.revisions.some(revision => String(revision.program.revision) === selectedPin) && <option value={selectedPin}>Revision {selectedPin} (pinned)</option>}
      {revisions.revisions.map(revision => <option key={revision.program.revision} value={revision.program.revision}>Revision {revision.program.revision}</option>)}
    </select></label>}
    {revisions.hasNextPage && <Button type="button" variant="ghost" disabled={disabled || revisions.isFetchingNextPage} onClick={() => void revisions.fetchNextPage()}>Load older revisions</Button>}
    {revisions.isSuccess && revisions.revisions.length === 0 && <p className="text-sm text-muted-foreground">Publish this program before using it here.</p>}
    {(revisions.error || pinned.error) && <p role="alert" className="text-destructive">{programError(revisions.error ?? pinned.error)}</p>}
    {value && <p className="text-xs text-muted-foreground">Pinned: {pinned.data?.definition.name ?? value.program_id} / revision {value.revision}{selected !== value.program_id ? '. Select a revision to replace this pin.' : ''}</p>}
    {pinned.data && <details className="text-sm"><summary>Program interfaces</summary><pre className="max-h-48 overflow-auto text-xs">{JSON.stringify({ inputs: pinned.data.definition.input_schema, outputs: pinned.data.definition.output_schema }, null, 2)}</pre></details>}
  </div>;
}
