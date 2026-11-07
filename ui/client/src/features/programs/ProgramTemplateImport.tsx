import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchBlueprintSummaries } from '@/api/blueprints';
import { importProgramTemplate } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { programError } from './authoring';

/** Templates enter the normal Program lifecycle; they never start an execution. */
export default function ProgramTemplateImport({ scope, teamId, disabled, onBusy, onImported }: {
  scope: string; teamId?: string; disabled: boolean;
  onBusy: (busy: boolean) => void; onImported: (id: string) => void;
}) {
  const [selected, setSelected] = useState('');
  const [expanded, setExpanded] = useState(false);
  const intent = useRef({ template: '', id: '' });
  const [error, setError] = useState('');
  const busy = useRef(false);
  const lifecycle = useRef(new AbortController());
  const templates = useQuery({ queryKey: ['program-templates', scope], enabled: expanded, queryFn: ({ signal }) => fetchBlueprintSummaries(teamId, signal) });
  useEffect(() => {
    const controller = new AbortController(); lifecycle.current = controller;
    return () => controller.abort();
  }, []);
  const capture = async () => {
    if (busy.current || disabled || !selected) return;
    const signal = lifecycle.current.signal;
    busy.current = true; onBusy(true); setError('');
    try {
      if (intent.current.template !== selected) intent.current = { template: selected, id: crypto.randomUUID() };
      const draft = await importProgramTemplate(intent.current.id, selected, teamId, signal);
      if (!signal.aborted) onImported(draft.definition.program_id);
    } catch (failure) {
      if (!signal.aborted) setError(programError(failure));
    } finally {
      if (!signal.aborted) { busy.current = false; onBusy(false); }
    }
  };
  return <details className="space-y-3 rounded border p-3" onToggle={event => setExpanded(event.currentTarget.open)}><summary>Import a workflow template</summary>
    <p className="text-sm text-muted-foreground">Capture an existing blueprint as a Program draft. Edit, publish, compose, and run it through the same Programs library.</p>
    <label className="block text-sm">Template<select aria-label="Program template" className="block w-full rounded border bg-background p-2" disabled={disabled} value={selected} onChange={event => setSelected(event.target.value)}>
      <option value="">Select a saved template</option>{templates.data?.map(template => <option key={template.blueprint_id} value={template.blueprint_id}>{template.name}</option>)}
    </select></label>
    <Button type="button" disabled={disabled || !selected} onClick={() => void capture()}>Import as Program</Button>
    {(error || templates.error) && <p role="alert" className="text-destructive">{error || programError(templates.error)}</p>}
  </details>;
}
