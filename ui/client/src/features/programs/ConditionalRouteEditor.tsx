import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { GraphDefinition, GraphRoute, ProgramBinding, ResourceSelection } from '@/api/programs';
import type { ResourceInstance } from '@/api/resources';
import { catalogService } from '@/api/catalog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import JsonField from '@/components/schema/JsonField';
import ResourcePicker from './ResourcePicker';
import ResourceAdoption from './ResourceAdoption';
import ExecutionSelectionFields from './ExecutionSelectionFields';
import { conditionLabels } from './graph-authoring';
import { programError } from './authoring';

/** Authored routes remain canonical graph data; evaluating them belongs to the engine. */
export default function ConditionalRouteEditor({ graph, source, names, profiles, scope, teamId, disabled, onChange, onResourceSelection }: {
  graph: GraphDefinition; source: string; names: Record<string, string>; profiles: string[];
  scope: string; teamId?: string; disabled: boolean; onChange: (graph: GraphDefinition) => void;
  onResourceSelection: (selection: ResourceSelection) => void;
}) {
  const route = graph.conditions.find(value => value.source === source);
  const [preferredKind, setPreferredKind] = useState<GraphRoute['kind']>('result');
  const kind = route?.kind ?? preferredKind;
  const ordinarySuccessors = (graph.edges[source] ?? []).length > 0;
  const [candidate, setCandidate] = useState<{ resource: ResourceInstance; adoption: ResourceSelection['adoption'] }>();
  const [hint, setHint] = useState<{ rid: string; type: string; name: string }>();
  const [label, setLabel] = useState('');
  const [target, setTarget] = useState('');
  const key = candidate?.resource.source?.key ?? (route?.kind === 'condition' ? route.condition : undefined);
  const snapshot = graph.resources.find(resource => resource.key.category === key?.category && resource.key.rid === key.rid);
  const type = candidate?.resource.type ?? snapshot?.type_key ?? (hint?.rid === key?.rid ? hint?.type : undefined);
  const contracts = useQuery({
    queryKey: ['program-element-contracts', scope, 'conditions', type], enabled: kind === 'condition' && !!type,
    queryFn: ({ signal }) => catalogService.fetchElementContracts('conditions', type!, signal),
  });
  const labels = conditionLabels(contracts.data?.output_schema ?? null);
  const symbolic = kind === 'condition' && contracts.data?.output_schema?.branch_type === 'symbolic';
  const selection: ProgramBinding = route?.kind === 'result' ? route.selection : { kind: 'path', path: ['results', source] };
  const setRoute = (replacement: GraphDefinition['conditions'][number] | undefined) => onChange({
    ...graph, conditions: [...graph.conditions.filter(value => value.source !== source), ...(replacement ? [replacement] : [])],
  });
  const selected = candidate?.resource;
  const applyCondition = () => {
    if (!candidate?.resource.source) return;
    onResourceSelection({ source: candidate.resource.source, adoption: candidate.adoption });
    setHint({ rid: candidate.resource.rid, type: candidate.resource.type, name: candidate.resource.name });
    setCandidate(undefined);
  };
  return <details className="space-y-3 rounded border p-3"><summary>Conditional routing</summary>
    <p className="text-xs text-muted-foreground">Routing runs after this block. Labels select outgoing destinations; true and false are boolean labels. Use a separate fork upstream for an always-active parallel path.</p>
    <label className="block text-sm">Route from<select aria-label="Route from" className="block w-full rounded border bg-background p-2" value={kind} disabled={disabled || !!route} onChange={event => { setPreferredKind(event.target.value as GraphRoute['kind']); setCandidate(undefined); setLabel(''); }}>
      <option value="result">Program or Operation result</option><option value="condition">Saved condition Element</option>
    </select></label>
    {route && <p className="text-xs text-muted-foreground">Remove this route to change its source type.</p>}
    {kind === 'result' && <JsonField label="Result selection binding" value={selection} objectOnly disabled={disabled} onChange={value => setRoute({ kind: 'result', source, selection: value as ProgramBinding, branches: route?.branches ?? {}, execution: route?.execution ?? {} })} />}
    {kind === 'result' && <p className="text-xs text-muted-foreground">Select this block's result or a field such as outcome. The value must be a label, boolean, or list of labels.</p>}
    {ordinarySuccessors && <p role="status" className="text-sm">Remove this block's ordinary outgoing connections before adding conditional routing.</p>}
    {kind === 'condition' && key && <p className="text-sm">Condition: {selected?.name ?? snapshot?.name ?? hint?.name ?? key.rid}</p>}
    {kind === 'condition' && <ResourcePicker scope={scope} teamId={teamId} disabled={disabled} category="conditions" title="Choose a saved condition" actionLabel="Select condition" onSelect={(resource, adoption) => { setCandidate({ resource, adoption }); setLabel(''); }} />}
    {candidate && route?.kind === 'condition' && <Button type="button" variant="outline" disabled={disabled} onClick={() => {
      if (!candidate.resource.source) return;
      applyCondition(); setRoute({ ...route, condition: candidate.resource.source.key });
    }}>Apply condition, preserving branch mappings</Button>}
    {kind === 'condition' && contracts.error && <p role="alert" className="text-destructive">{programError(contracts.error)}</p>}
    {(kind === 'result' || key) && <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Branch label{symbolic ? <select aria-label="Branch label" className="block w-full rounded border bg-background p-2" value={label} disabled={disabled} onChange={event => setLabel(event.target.value)}>
        <option value="">Select a condition label</option>{labels.map(option => <option key={option.value} value={option.value}>{option.label} ({option.value})</option>)}
      </select> : <Input aria-label="Branch label" value={label} disabled={disabled} onChange={event => setLabel(event.target.value)} />}</label>
      <label className="text-sm">Branch destination<select aria-label="Branch destination" className="block w-full rounded border bg-background p-2" value={target} disabled={disabled} onChange={event => setTarget(event.target.value)}>
        <option value="">Select a block</option>{graph.steps.map(step => <option key={step.uid} value={step.uid}>{names[step.uid]}</option>)}
      </select></label></div>
      <Button type="button" variant="outline" disabled={disabled || ordinarySuccessors || !label.trim() || !target || Object.hasOwn(route?.branches ?? {}, label)} onClick={() => {
        const branches = { ...route?.branches, [label]: target };
        if (kind === 'result') setRoute({ kind, source, selection, branches, execution: route?.execution ?? {} });
        else if (key) {
          applyCondition();
          setRoute({ kind, source, condition: key, branches, execution: route?.execution ?? { profile: candidate?.resource.execution?.profile ?? null } });
        }
        setLabel(''); setTarget('');
      }}>Add branch</Button>
      {route && Object.entries(route.branches).map(([name, destination]) => <div key={name} className="flex items-center gap-2 text-sm"><span className="min-w-0 flex-1 break-words">{name} → {names[destination] ?? destination}</span><Button type="button" variant="ghost" disabled={disabled} aria-label={`Remove branch ${name}`} onClick={() => {
        const branches = Object.fromEntries(Object.entries(route.branches).filter(([key]) => key !== name));
        setRoute(Object.keys(branches).length ? { ...route, branches } : undefined);
      }}>Remove</Button></div>)}
    </div>}
    {route && <><ExecutionSelectionFields label={route.kind === 'result' ? 'Routing' : 'Condition'} value={route.execution} profiles={profiles} environments={Object.keys(graph.environments)} disabled={disabled} onChange={execution => setRoute({ ...route, execution })} />
      {route.kind === 'condition' && <ResourceAdoption resource={route.condition} scope={scope} teamId={teamId} disabled={disabled} onSelect={onResourceSelection} />}
      <Button type="button" variant="outline" disabled={disabled} onClick={() => { setRoute(undefined); setCandidate(undefined); setHint(undefined); }}>Remove conditional routing</Button></>}
  </details>;
}
