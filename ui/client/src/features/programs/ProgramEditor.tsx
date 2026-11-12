import React, { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { publishProgram, saveProgram, validateProgramDraft, type CustomCoordinatorDefinition, type GraphDefinition, type ProgramDefinition, type ProgramDescriptor, type ProgramDraft, type ProgramPresentation, type ProgramSummary, type ProgramValidation } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { WorkspaceIdentity } from '@/hooks/use-workspace-identity';
import type { JsonObject } from '@shared/json';
import { configurationDefaults, emptyGraphDefinition, programError } from './authoring';
import JsonField from '@/components/schema/JsonField';
import ProgramConfiguration from './ProgramConfiguration';
import ProgramDependencies from './ProgramDependencies';
import ProgramGraphEditor from './ProgramGraphEditor';
import ProgramInvocation from '@/components/executions/ProgramInvocation';
import { useProgramRevisions } from './queries';
import { activeResourceSelections, queueResourceSelection, type PendingResourceSelection } from './resource-selections';
import ProgramReadiness from './ProgramReadiness';
import { useProgramInterface } from './use-program-interface';

function emptyDefinition(id: string, owner: WorkspaceIdentity): ProgramDefinition {
  return {
    program_id: id, name: '', owner: { type: owner.isTeam ? 'team' : 'user', id: owner.userId, display_name: owner.displayName },
    implementation: emptyGraphDefinition(),
    input_schema: { type: 'object' }, output_schema: { type: 'object' }, execution_profile: null,
  };
}

/** Drafts may omit work, but must not silently save stale or malformed field values. */
function reportValidity(form: HTMLFormElement | null, intent: 'save' | 'publish'): boolean {
  if (!form) return false;
  for (const field of form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea')) {
    const unfinished = intent === 'save' && field.validity.valueMissing && !field.validity.customError && !field.validity.badInput && !field.hasAttribute('data-draft-required');
    if (field.willValidate && !unfinished && !field.reportValidity()) return false;
  }
  return true;
}

export default function ProgramEditor({ id, initial, owner, scope, catalog, programs, profiles, onState }: {
  id: string; initial?: ProgramDraft; owner: WorkspaceIdentity; scope: string;
  catalog: ProgramDescriptor[]; programs: ProgramSummary[]; profiles: string[];
  onState: (dirty: boolean, busy: boolean) => void;
}) {
  const queries = useQueryClient();
  const [definition, setDefinition] = useState(initial?.definition ?? emptyDefinition(id, owner));
  const [presentation, setPresentation] = useState<ProgramPresentation>(initial?.presentation ?? { positions: {} });
  const [version, setVersion] = useState(initial?.version ?? 0);
  const [saved, setSaved] = useState(initial ? JSON.stringify([initial.definition, initial.presentation]) : '');
  const [busy, setBusy] = useState(false);
  const [configurationBusy, setConfigurationBusy] = useState(false);
  const [invocationBusy, setInvocationBusy] = useState(false);
  const [edited, setEdited] = useState(false);
  const [resourceSelections, setResourceSelections] = useState<PendingResourceSelection[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [runRevision, setRunRevision] = useState<number>();
  const [readiness, setReadiness] = useState<ProgramValidation>();
  const form = useRef<HTMLFormElement>(null);
  const lifecycle = useRef(new AbortController());
  const action = useRef(false);
  const implementation = definition.implementation;
  const descriptor = catalog.find(value => implementation.kind === 'graph' ? value.kind === 'graph' : value.kind === 'application' && value.key === implementation.implementation && value.version === implementation.version);
  const interfacePreview = useProgramInterface(definition, implementation.kind === 'application', owner.teamId);
  const dirty = edited || resourceSelections.length > 0 || saved !== JSON.stringify([definition, presentation]);
  const revisions = useProgramRevisions(id, scope, owner.teamId, version > 0);
  useEffect(() => { onState(dirty, busy || configurationBusy || invocationBusy); }, [dirty, busy, configurationBusy, invocationBusy, onState]);
  useEffect(() => {
    if (runRevision === undefined && revisions.revisions.length) setRunRevision(revisions.revisions[0].program.revision);
  }, [revisions.revisions, runRevision]);
  useEffect(() => {
    const controller = new AbortController(); lifecycle.current = controller;
    return () => controller.abort();
  }, []);
  const changeImplementation = (value: CustomCoordinatorDefinition | GraphDefinition) => {
    setResourceSelections(previous => activeResourceSelections(value, previous));
    setDefinition(previous => ({ ...previous, implementation: value }));
  };
  const perform = async (intent: 'save' | 'publish', operation: (signal: AbortSignal) => Promise<void>) => {
    if (action.current || configurationBusy || !reportValidity(form.current, intent)) return;
    const controller = lifecycle.current;
    action.current = true; setBusy(true); setError(''); setNotice('');
    try { await operation(controller.signal); }
    catch (failure) { if (!controller.signal.aborted) setError(programError(failure)); }
    finally { if (!controller.signal.aborted) { action.current = false; setBusy(false); } }
  };
  const save = async (signal: AbortSignal): Promise<ProgramDraft> => {
    if (version && !dirty) return { definition, presentation, version };
    const draft = await saveProgram({ definition, presentation, expected_version: version, resource_selections: resourceSelections.map(({ capturedDigest, ...selection }) => selection) }, owner.teamId, signal);
    if (!signal.aborted) {
      setDefinition(draft.definition); setPresentation(draft.presentation); setVersion(draft.version);
      setEdited(false);
      setResourceSelections([]);
      setSaved(JSON.stringify([draft.definition, draft.presentation])); setNotice(`Saved draft version ${draft.version}.`);
      void queries.invalidateQueries({ queryKey: ['program-library', scope] });
    }
    return draft;
  };
  const chooseSource = (selected: string) => {
    setResourceSelections([]);
    const selectedDescriptor = catalog.find(value => JSON.stringify([value.key, value.version]) === selected);
    if (!selectedDescriptor) return;
    setDefinition(previous => ({ ...previous,
      implementation: selectedDescriptor.kind === 'graph' ? emptyGraphDefinition() : {
        kind: 'application', implementation: selectedDescriptor.key, version: selectedDescriptor.version,
        config: configurationDefaults(selectedDescriptor), children: {}, environments: {}, child_environment_imports: {},
      },
      input_schema: selectedDescriptor.input_schema ?? { type: 'object' },
      output_schema: selectedDescriptor.output_schema ?? { type: 'object' },
    }));
  };
  const selectedSource = descriptor ? JSON.stringify([descriptor.key, descriptor.version]) : '';
  const runnable = runRevision;
  const available = programs.filter(program => program.program_id !== id);
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-semibold">{version ? definition.name : 'New program'}</h2><span className="text-sm text-muted-foreground">{version ? `Draft version ${version}${dirty ? ' / unsaved changes' : ''}` : 'Unsaved draft'}</span></div>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form ref={form} noValidate className="space-y-5" onChange={() => setEdited(true)} onSubmit={event => { event.preventDefault(); void perform('save', async signal => { await save(signal); }); }}>
      <fieldset disabled={busy || configurationBusy} className="space-y-4">
        <label className="block space-y-1 text-sm"><span>Program name</span><Input className="text-inherit" aria-label="Program name" required data-draft-required value={definition.name} onChange={event => setDefinition({ ...definition, name: event.target.value })} /></label>
        <label className="block space-y-1 text-sm"><span>Start from</span><select aria-label="Program source" className="block w-full rounded border bg-background p-2" value={selectedSource} disabled={busy || version > 0} required data-draft-required onChange={event => chooseSource(event.target.value)}>
          <option value="">Choose how to define the work</option>
          {catalog.map(value => <option key={JSON.stringify([value.key, value.version])} value={JSON.stringify([value.key, value.version])}>{value.name}</option>)}
        </select></label>
        {descriptor && implementation.kind === 'application' && <><p className="text-sm text-muted-foreground">{descriptor.description}</p>
          <ProgramConfiguration key={JSON.stringify([descriptor.key, descriptor.version])} descriptor={descriptor} config={implementation.config} disabled={busy || configurationBusy} scope={scope} teamId={owner.teamId} profiles={profiles} environments={Object.keys(implementation.environments)} onBusyChange={setConfigurationBusy} onResourceSelection={selection => setResourceSelections(previous => queueResourceSelection(previous, selection))} onChange={config => changeImplementation({ ...implementation, config })} />
          <ProgramDependencies children={implementation.children} declarations={interfacePreview.preview?.interface?.dependencies} resolving={interfacePreview.pending} resolutionIssue={interfacePreview.error ?? interfacePreview.preview?.issues[0]?.message} onChange={children => changeImplementation({ ...implementation, children, child_environment_imports: Object.fromEntries(Object.entries(implementation.child_environment_imports).filter(([name]) => !Object.hasOwn(implementation.children, name) || Object.hasOwn(children, name))) })} programs={available} teamId={owner.teamId} scope={scope} disabled={busy} />
        </>}
        {implementation.kind === 'graph' && <ProgramGraphEditor graph={implementation} presentation={presentation} onChange={changeImplementation} onPresentation={setPresentation} programs={available} profiles={profiles} teamId={owner.teamId} scope={scope} disabled={busy} onResourceSelection={selection => setResourceSelections(previous => queueResourceSelection(previous, selection))} />}
        {resourceSelections.length > 0 && <p className="text-sm text-muted-foreground">{resourceSelections.length} saved element selection(s) will be resolved when this draft is saved.</p>}
        <details className="space-y-3"><summary>Execution settings</summary>
          <label className="block text-sm">Execution profile<select aria-label="Execution profile" className="block w-full rounded border bg-background p-2" value={definition.execution_profile ?? ''} onChange={event => setDefinition({ ...definition, execution_profile: event.target.value || null })}>
            <option value="">Platform default</option>{definition.execution_profile && !profiles.includes(definition.execution_profile) && <option value={definition.execution_profile}>{definition.execution_profile} (unavailable)</option>}{profiles.map(profile => <option key={profile}>{profile}</option>)}
          </select></label>
          <JsonField label="Named environments" value={implementation.environments} objectOnly disabled={busy} onChange={value => changeImplementation({ ...implementation, environments: value as Record<string, string> })} />
          {implementation.kind === 'application' && <JsonField label="Child Program environment imports" value={implementation.child_environment_imports} objectOnly disabled={busy} onChange={value => changeImplementation({ ...implementation, child_environment_imports: value as Record<string, Record<string, string>> })} />}
        </details>
        <details className="space-y-3"><summary>Public input and output contracts</summary>
          <JsonField label="Input schema" value={definition.input_schema} objectOnly disabled={busy} onChange={value => setDefinition({ ...definition, input_schema: value as JsonObject })} />
          <JsonField label="Output schema" value={definition.output_schema} objectOnly disabled={busy} onChange={value => setDefinition({ ...definition, output_schema: value as JsonObject })} />
        </details>
      </fieldset>
      <div className="flex gap-3"><Button type="submit" variant="outline" disabled={busy || configurationBusy || !selectedSource}>Save draft</Button>
        <Button type="button" variant="outline" disabled={busy || configurationBusy || !selectedSource} onClick={() => void perform('save', async signal => {
          const draft = await save(signal);
          const report = await validateProgramDraft(id, draft.version, owner.teamId, signal);
          if (!signal.aborted) setReadiness(report);
        })}>Check readiness</Button>
        <Button type="button" disabled={busy || configurationBusy || !selectedSource} onClick={() => void perform('publish', async signal => {
          const draft = await save(signal);
          const revision = await publishProgram(id, draft.version, owner.teamId, signal);
          if (!signal.aborted) {
            setRunRevision(revision.revision); setNotice(`Published ${revision.definition.name} / revision ${revision.revision}.`);
            void queries.invalidateQueries({ queryKey: ['program-revisions', scope, id] });
          }
        })}>Publish program</Button>
      </div>
    </form>
    {readiness && <ProgramReadiness report={readiness} current={readiness.version === version && !dirty} />}
    {revisions.error && <p role="alert" className="text-destructive">{programError(revisions.error)}</p>}
    {(revisions.revisions.length || runnable) ? <section className="space-y-3">
      <label className="block text-sm">Published revision<select aria-label="Run revision" className="block w-full rounded border bg-background p-2" disabled={invocationBusy} value={runnable ?? ''} onChange={event => setRunRevision(Number(event.target.value))}>
        {runnable && !revisions.revisions.some(value => value.program.revision === runnable) && <option value={runnable}>Revision {runnable}</option>}
        {revisions.revisions.map(value => <option key={value.program.revision} value={value.program.revision}>Revision {value.program.revision}</option>)}
      </select></label>
      {revisions.hasNextPage && <Button variant="ghost" disabled={revisions.isFetchingNextPage} onClick={() => void revisions.fetchNextPage()}>Load older revisions</Button>}
      <p className="text-xs text-muted-foreground">Runs use the selected immutable revision. Draft edits do not change existing callers or executions.</p>
      {runnable && <ProgramInvocation key={runnable} program={{ program_id: id, revision: runnable }} scope={scope} teamId={owner.teamId} onBusyChange={setInvocationBusy} />}
    </section> : null}
  </div>;
}
