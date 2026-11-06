import React, { useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, MarkerType, type Connection, type Edge, type Node, type NodeChange } from 'react-flow-renderer';
import type { GraphDefinition, GraphStep, ProgramBindings, ProgramProjection, ProgramPresentation, ProgramRef, ProgramSummary, ResourceSelection } from '@/api/programs';
import { Button } from '@/components/ui/button';
import JsonField from '@/components/schema/JsonField';
import ProgramPicker from './ProgramPicker';
import ResourcePicker from './ResourcePicker';
import ResourceAdoption from './ResourceAdoption';
import ElementContracts from './ElementContracts';
import ConditionalRouteEditor from './ConditionalRouteEditor';
import ExecutionSelectionFields from './ExecutionSelectionFields';
import { branchEdgeId, orderingEdgeId, removeGraphEdges, removeGraphStep } from './graph-authoring';
import { programTargetLabel } from './authoring';

/** The canvas projects the canonical definition; it owns no second executable model. */
export default function ProgramGraphEditor({ graph, presentation, onChange, onPresentation, programs, profiles, teamId, scope, disabled, onResourceSelection }: {
  graph: GraphDefinition; presentation: ProgramPresentation; onChange: (value: GraphDefinition) => void;
  onPresentation: (value: ProgramPresentation) => void; programs: ProgramSummary[];
  teamId?: string; scope: string; disabled: boolean;
  profiles: string[]; onResourceSelection: (selection: ResourceSelection) => void;
}) {
  const [selected, setSelected] = useState('');
  const [selectedEdge, setSelectedEdge] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [call, setCall] = useState<ProgramRef>();
  const [elementTypes, setElementTypes] = useState<Record<string, string>>({});
  const step = graph.steps.find(value => value.uid === selected);
  const names = Object.fromEntries(graph.steps.map(value => [value.uid, value.kind === 'program' ? programTargetLabel(value.program, programs) : String(value.metadata.display_name || graph.resources.find(resource => resource.key.rid === value.element.rid && resource.key.category === value.element.category)?.name || value.element.rid)]));
  const selectedType = step && step.kind !== 'program' ? graph.resources.find(resource => resource.key.rid === step.element.rid && resource.key.category === step.element.category)?.type_key ?? elementTypes[step.uid] : undefined;
  const nodes: Node[] = useMemo(() => graph.steps.map((step, index) => ({
    id: step.uid, position: presentation.positions[step.uid] ?? { x: 80 + index * 240, y: 100 }, selected: selected === step.uid,
    data: { label: step.kind === 'program' ? programTargetLabel(step.program, programs) : step.metadata.display_name || graph.resources.find(resource => resource.key.rid === step.element.rid && resource.key.category === step.element.category)?.name || step.element.rid },
  })), [graph.steps, graph.resources, presentation.positions, programs, selected]);
  const edges: Edge[] = Object.entries(graph.edges).flatMap(([source, targets]) => targets.map(target => ({ id: orderingEdgeId(source, target), source, target, markerEnd: { type: MarkerType.ArrowClosed } })));
  for (const route of graph.conditions) for (const [label, target] of Object.entries(route.branches)) edges.push({ id: branchEdgeId(route.source, label, target), source: route.source, target, label, markerEnd: { type: MarkerType.ArrowClosed } });
  const update = (replacement: GraphStep) => onChange({ ...graph, steps: graph.steps.map(value => value.uid === replacement.uid ? replacement : value) });
  const connect = ({ source, target }: Connection) => {
    if (disabled || !source || !target) return;
    if (graph.conditions.some(route => route.source === source)) {
      setConnectionError('This block uses conditional routing. Add a labeled branch in its routing settings.');
      setSelected(source); return;
    }
    setConnectionError('');
    if (!(graph.edges[source] ?? []).includes(target)) onChange({ ...graph, edges: { ...graph.edges, [source]: [...(graph.edges[source] ?? []), target] } });
  };
  const move = (changes: NodeChange[]) => {
    if (disabled) return;
    const positions = { ...presentation.positions };
    let moved = false;
    for (const change of changes) if (change.type === 'position' && change.position) { positions[change.id] = change.position; moved = true; }
    if (moved) onPresentation({ ...presentation, positions });
  };
  return <div className="space-y-4">
    <div className="grid gap-4 lg:grid-cols-[1fr_260px]"><div className="h-[450px] rounded border" aria-label="Program composition canvas">
      <ReactFlow nodes={nodes} edges={edges} onConnect={connect} onNodesChange={move} onNodeClick={(_, node) => { setSelected(node.id); setSelectedEdge(''); }}
        onEdgeClick={(_, edge) => setSelectedEdge(edge.id)} deleteKeyCode={null}
        nodesDraggable={!disabled} nodesConnectable={!disabled} elementsSelectable fitView><Background /><Controls /></ReactFlow>
    </div><div className="max-h-[450px] space-y-4 overflow-auto rounded border p-3">
      <ResourcePicker scope={scope} teamId={teamId} disabled={disabled} onSelect={(resource, adoption) => {
        if (!resource.source) return;
        const uid = crypto.randomUUID();
        const common = { uid, element: resource.source.key, execution: { profile: resource.execution?.profile ?? null }, max_attempts: 1, metadata: { display_name: resource.name } };
        const step: GraphStep = resource.category === 'operations' ? { ...common, kind: 'operation', inputs: {}, outputs: {} } : { ...common, kind: 'element', description: '' };
        onResourceSelection({ source: resource.source, adoption });
        setElementTypes(previous => ({ ...previous, [uid]: resource.type }));
        onChange({ ...graph, steps: [...graph.steps, step], entry: graph.entry || uid, exit: graph.exit || uid });
        setSelected(uid);
      }} />
      <h3 className="font-medium">Add a program block</h3>
      <ProgramPicker value={call} onChange={setCall} programs={programs} teamId={teamId} scope={scope} disabled={disabled} label="Reusable program" />
      <Button type="button" variant="outline" disabled={disabled || !call} onClick={() => {
        if (!call) return;
        const uid = crypto.randomUUID();
        onChange({ ...graph, steps: [...graph.steps, { kind: 'program', uid, program: call, inputs: {}, outputs: {}, environment_imports: {}, max_attempts: 1, metadata: {} }], entry: graph.entry || uid, exit: graph.exit || uid });
        setSelected(uid);
      }}>Add program block</Button>
    </div></div>
    <p className="text-xs text-muted-foreground">Connect blocks using their handles. Connections define execution order; data mappings are configured separately.</p>
    {connectionError && <p role="alert" className="text-sm">{connectionError}</p>}
    {edges.some(edge => edge.id === selectedEdge) && <Button type="button" variant="outline" disabled={disabled} onClick={() => { onChange(removeGraphEdges(graph, new Set([selectedEdge]))); setSelectedEdge(''); }}>Remove selected connection</Button>}
    <div className="grid gap-3 sm:grid-cols-2">{(['entry', 'exit'] as const).map(field => <label key={field} className="text-sm">{field === 'entry' ? 'Start block' : 'Finish block'}<select aria-label={field === 'entry' ? 'Start block' : 'Finish block'} className="block w-full rounded border bg-background p-2" value={graph[field]} disabled={disabled} required onChange={event => onChange({ ...graph, [field]: event.target.value })}>
      <option value="">Select a block</option>{graph.steps.map(value => <option key={value.uid} value={value.uid}>{names[value.uid]}</option>)}
    </select></label>)}</div>
    <label className="block text-sm">Join policy<select aria-label="Join policy" className="block w-full rounded border bg-background p-2" value={graph.join_policy ?? 'active'} disabled={disabled} onChange={event => onChange({ ...graph, join_policy: event.target.value as 'active' | 'all' })}>
      <option value="active">Wait for active paths</option><option value="all">Require all predecessors</option>
    </select></label>
    <label className="block text-sm">State writers<select aria-label="State writers" className="block w-full rounded border bg-background p-2" value={graph.write_policy ?? 'ordered'} disabled={disabled} onChange={event => onChange({ ...graph, write_policy: event.target.value as 'ordered' | 'reduce' })}>
      <option value="ordered">Require ordered writers</option><option value="reduce">Use declared channel reducers</option>
    </select></label>
    {step && <section key={step.uid} className="space-y-3 rounded border p-3"><div className="flex items-center justify-between gap-3"><h3 className="font-medium">Selected block: {names[step.uid]}</h3>
      <Button type="button" variant="outline" disabled={disabled} onClick={() => {
        onChange(removeGraphStep(graph, step.uid));
        onPresentation({ ...presentation, positions: Object.fromEntries(Object.entries(presentation.positions).filter(([uid]) => uid !== step.uid)) });
        setSelected('');
      }}>Remove block</Button></div>
      {step.kind === 'program' && <>
        {!('program_id' in step.program) && <p className="text-sm">{programTargetLabel(step.program, programs)} — saved within this Program.</p>}
        <ProgramPicker label={'program_id' in step.program ? 'Called program' : 'Replace inline body with published program'} value={'program_id' in step.program ? step.program : undefined} programs={programs} teamId={teamId} scope={scope} disabled={disabled} onChange={program => update({ ...step, program })} />
      </>}
      {step.kind !== 'program' && <ResourceAdoption resource={step.element} scope={scope} teamId={teamId} disabled={disabled} onSelect={onResourceSelection} />}
      {step.kind !== 'program' && selectedType && <ElementContracts category={step.element.category} type={selectedType} scope={scope} />}
      {step.kind !== 'element' && <div className="grid gap-3 md:grid-cols-2">
        <JsonField key={`${step.uid}-inputs`} label="Block input projection" value={step.inputs ?? {}} objectOnly disabled={disabled} onChange={value => update({ ...step, inputs: value as ProgramProjection })} />
        <JsonField key={`${step.uid}-outputs`} label="Block output bindings" value={step.outputs ?? {}} objectOnly disabled={disabled} onChange={value => update({ ...step, outputs: value as ProgramBindings })} />
      </div>}
      {step.kind === 'program' && <JsonField key={`${step.uid}-imports`} label="Imported environments" value={step.environment_imports} objectOnly disabled={disabled} onChange={value => update({ ...step, environment_imports: value as Record<string, string> })} />}
      {step.kind !== 'program' && <ExecutionSelectionFields label="Block" value={step.execution} profiles={profiles} environments={Object.keys(graph.environments)} disabled={disabled} onChange={execution => update({ ...step, execution })} />}
      <ConditionalRouteEditor graph={graph} source={step.uid} names={names} profiles={profiles} scope={scope} teamId={teamId} disabled={disabled} onChange={onChange} onResourceSelection={onResourceSelection} />
    </section>}
    <details className="space-y-3"><summary>Program data mappings</summary><JsonField label="Program input bindings" value={graph.inputs} objectOnly disabled={disabled} onChange={value => onChange({ ...graph, inputs: value as ProgramBindings })} />
      <JsonField label="Program output projection" value={graph.outputs} objectOnly disabled={disabled} onChange={value => onChange({ ...graph, outputs: value as ProgramProjection })} />
    </details>
  </div>;
}
