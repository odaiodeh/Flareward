/** Canonical program clients publish and run pinned composition through native services. */
import assert from 'node:assert/strict';
import api from '../client/src/http/axiosAgentConfig';
import { cancelProgramExecution, getProgramDraft, getProgramRevision, inspectProgramExecution, listProgramExecutionChildren, listProgramRevisions, listPrograms, programImplementations, publishProgram, saveProgram, startProgram, validateProgramDraft, type ProgramBody, type ProgramDefinition } from '../client/src/api/programs';
import { captureResourceSnapshot, createResource, listResourcePage, updateResource } from '../client/src/api/resources';
import type { JsonValue } from '../shared/json';
import { catalogService } from '../client/src/api/catalog';
import { removeGraphEdges, orderingEdgeId } from '../client/src/features/programs/graph-authoring';
import { isRecord } from '../client/src/lib/json';

async function terminal(id: string) {
  const deadline = Date.now() + 20_000;
  let execution = await inspectProgramExecution(id);
  while (!['completed', 'failed', 'cancelled'].includes(execution.phase) && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 20)); execution = await inspectProgramExecution(id);
  }
  assert.ok(['completed', 'failed', 'cancelled'].includes(execution.phase));
  return execution;
}

async function completed(id: string) {
  const execution = await terminal(id);
  assert.deepEqual(execution.work_limits, { max_dispatches: 10000, max_children: 1000, max_depth: 32 });
  assert.deepEqual(execution.admitted_profiles?.profiles, ['process', 'thread']);
  assert.equal(execution.phase, 'completed');
  return execution;
}

async function verifyInstalledProgramModels(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const descriptor = (await programImplementations()).find(value => value.key === 'typed_program')!;
  assert.ok(descriptor.input_schema && descriptor.output_schema);
  assert.ok(isRecord(descriptor.output_schema.properties));
  assert.ok(Object.hasOwn(descriptor.output_schema.properties, 'summary'));
  assert.ok(Object.hasOwn(descriptor.output_schema.properties, 'label'));
  assert.ok(!Object.hasOwn(descriptor.output_schema.properties, 'wireLabel'));
  const definition: ProgramDefinition = { ...base, program_id: 'client-typed-program', name: 'Typed Program', input_schema: descriptor.input_schema, output_schema: descriptor.output_schema, implementation: {
    kind: 'application', implementation: descriptor.key, version: descriptor.version, config: {}, children: {}, environments: {}, child_environment_imports: {},
  } };
  const saved = await saveProgram({ definition, expected_version: 0 });
  const published = await publishProgram(definition.program_id, saved.version);
  const program = { program_id: definition.program_id, revision: published.revision };
  await startProgram({ execution_id: 'client-installed-models', program, inputs: { amountAlias: 3, label: 'client' } });
  const result = await completed('client-installed-models');
  assert.deepEqual(result.result, { total: 6, label: 'client', tags: [], summary: 'client:6' });
  await startProgram({ execution_id: 'client-invalid-model', program, inputs: { amountAlias: 3, label: 'private-model-input' } });
  const invalid = await terminal('client-invalid-model');
  assert.equal(invalid.phase, 'failed');
  assert.equal(invalid.failure?.kind, 'contract');
  assert.ok(!invalid.failure?.message.includes('private-model-input'));
  const map: ProgramDefinition = { ...base, program_id: 'client-typed-map', name: 'Typed Map', implementation: {
    kind: 'application', implementation: 'map', version: '1', config: { inputs: { label: { kind: 'literal', value: 'mapped' } } }, children: { body: program }, environments: {}, child_environment_imports: {},
  } };
  const draft = await saveProgram({ definition: map, expected_version: 0 });
  const report = await validateProgramDraft(map.program_id, draft.version);
  assert.equal(report.valid, false);
  assert.equal(report.issues[0].code, 'INVALID_BINDING');
  assert.deepEqual(report.issues[0].path, ['implementation', 'children', 'body', 'amount']);
  await assert.rejects(publishProgram(map.program_id, draft.version));
  assert.ok(map.implementation.kind === 'application');
  map.implementation.config.inputs = { amountAlias: { kind: 'path', path: ['item'] }, label: { kind: 'literal', value: 'mapped' } };
  const fixed = await saveProgram({ definition: map, expected_version: draft.version });
  assert.equal((await validateProgramDraft(map.program_id, fixed.version)).valid, true);
  const mapped = await publishProgram(map.program_id, fixed.version);
  await startProgram({ execution_id: 'client-typed-map', program: { program_id: map.program_id, revision: mapped.revision }, inputs: { items: [2, 3] } });
  const observed = await completed('client-typed-map');
  assert.ok(isRecord(observed.result) && Array.isArray(observed.result.items));
  assert.deepEqual(observed.result.items.map(item => {
    assert.ok(isRecord(item) && isRecord(item.value)); return item.value.summary;
  }), ['mapped:4', 'mapped:6']);
  assert.equal((await listProgramExecutionChildren(observed.execution_id)).length, 2);
}

async function verifyBindingReadiness() {
  const savedOperation = await getProgramDraft('saved-operation');
  assert.ok(savedOperation.definition.implementation.kind === 'graph');
  const graph = savedOperation.definition.implementation;
  assert.ok(graph.steps[0].kind === 'operation');
  const definition: ProgramDefinition = { ...savedOperation.definition, program_id: 'client-binding-readiness', name: 'Binding readiness', implementation: { ...graph, steps: [{ ...graph.steps[0], inputs: {} }] } };
  const draft = await saveProgram({ definition, expected_version: 0 });
  const report = await validateProgramDraft(definition.program_id, draft.version);
  assert.equal(report.valid, false);
  assert.equal(report.issues[0].code, 'INVALID_BINDING');
  assert.deepEqual(report.issues[0].path, ['implementation', 'steps', 0, 'inputs', 'text']);
  await assert.rejects(publishProgram(definition.program_id, draft.version));
  assert.deepEqual((await listProgramRevisions(definition.program_id)).revisions, []);
  const fixed = await saveProgram({ definition: { ...definition, implementation: graph }, expected_version: draft.version });
  assert.equal((await validateProgramDraft(definition.program_id, fixed.version)).valid, true);
  const revision = await publishProgram(definition.program_id, fixed.version);
  await startProgram({ execution_id: 'client-binding-ready', program: { program_id: definition.program_id, revision: revision.revision }, inputs: { name: 'ready' } });
  assert.deepEqual((await completed('client-binding-ready')).result, { answer: 'changed:client-middle:ready' });
}

async function verifyWholeValueBindings(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const definition: ProgramDefinition = { ...base, program_id: 'client-array-flow', name: 'Array flow', input_schema: { type: 'array' }, output_schema: { type: 'array' }, implementation: {
    kind: 'graph', steps: [{ kind: 'operation', uid: 'array', element: { category: 'operations', rid: 'array' }, inputs: { kind: 'path', path: ['input'] }, outputs: {}, execution: {}, max_attempts: 1, metadata: {} }],
    resources: [{ key: { category: 'operations', rid: 'array' }, type_key: 'platform_array_operation', name: 'Array', config: {}, implementation_version: '1.0.0' }],
    edges: {}, conditions: [], entry: 'array', exit: 'array', inputs: {}, outputs: { kind: 'path', path: ['results', 'array'] }, environments: {}, recursion_limit: 100, join_policy: 'all',
  } };
  const draft = await saveProgram({ definition, expected_version: 0 });
  assert.equal((await validateProgramDraft(definition.program_id, draft.version)).valid, true);
  const published = await publishProgram(definition.program_id, draft.version);
  const program = { program_id: definition.program_id, revision: published.revision };
  const frozen = await getProgramRevision(program);
  assert.ok(frozen.definition.implementation.kind === 'graph');
  assert.equal(frozen.definition.implementation.join_policy, 'all');
  await startProgram({ execution_id: 'client-array-flow', program, inputs: [2, 3] });
  assert.deepEqual((await completed('client-array-flow')).result, [4, 6]);
  const parent: ProgramDefinition = { ...base, program_id: 'client-array-caller', name: 'Array caller', input_schema: { type: 'array' }, output_schema: { type: 'array' }, implementation: {
    kind: 'graph', steps: [
      { kind: 'program', uid: 'first', program, inputs: { kind: 'path', path: ['input'] }, outputs: {}, environment_imports: {}, max_attempts: 1, metadata: {} },
      { kind: 'program', uid: 'second', program, inputs: { kind: 'path', path: ['results', 'first'] }, outputs: {}, environment_imports: {}, max_attempts: 1, metadata: {} },
    ],
    resources: [], edges: {}, conditions: [], entry: 'first', exit: 'second', inputs: {}, outputs: { kind: 'path', path: ['results', 'first'] }, environments: {}, recursion_limit: 100, join_policy: 'active',
  } };
  const saved = await saveProgram({ definition: parent, expected_version: 0 });
  const readiness = await validateProgramDraft(parent.program_id, saved.version);
  assert.equal(readiness.valid, false);
  assert.equal(readiness.issues[0].code, 'INVALID_BINDING');
  assert.deepEqual(readiness.issues[0].path, ['implementation', 'steps', 1, 'inputs']);
  await assert.rejects(publishProgram(parent.program_id, saved.version));
  assert.ok(parent.implementation.kind === 'graph');
  parent.implementation.edges = { first: ['second'] };
  parent.implementation.outputs = { kind: 'path', path: ['results', 'second'] };
  const fixed = await saveProgram({ definition: parent, expected_version: saved.version });
  const root = await publishProgram(parent.program_id, fixed.version);
  await startProgram({ execution_id: 'client-array-caller', program: { program_id: parent.program_id, revision: root.revision }, inputs: [1, 4] });
  const execution = await completed('client-array-caller');
  assert.deepEqual(execution.result, [4, 16]);
  const children = await listProgramExecutionChildren(execution.execution_id);
  assert.equal(children.length, 2);
  assert.ok(children.every(child => child.program.program_id === program.program_id && child.program.revision === program.revision));
  assert.ok(children.some(child => JSON.stringify(child.inputs) === '[1,4]'));
  assert.ok(children.some(child => JSON.stringify(child.inputs) === '[2,8]'));
}

async function verifyIncompleteConfiguration(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const definition: ProgramDefinition = { ...base, program_id: 'client-incomplete-config', name: 'Incomplete configuration', implementation: {
    kind: 'application', implementation: 'draft_configured', version: '1', environments: {}, child_environment_imports: {}, children: {}, config: {
      providers: { primary: { kind: 'remote', budget: 1, credential: { apiKey: 'client-provider-private' } } },
      connections: [{ auth: { key: 'client-connection-private' } }], private: { password: 'client-settings-private' },
    },
  } };
  const saved = await saveProgram({ definition, expected_version: 0 });
  assert.ok(!JSON.stringify(saved).includes('client-provider-private'));
  assert.ok(!JSON.stringify(saved).includes('client-connection-private'));
  assert.ok(!JSON.stringify(saved).includes('client-settings-private'));
  assert.deepEqual(await getProgramDraft(definition.program_id), saved);
  assert.equal((await validateProgramDraft(definition.program_id, saved.version)).valid, false);
  await assert.rejects(publishProgram(definition.program_id, saved.version));
  assert.deepEqual((await listProgramRevisions(definition.program_id)).revisions, []);
  assert.equal(saved.definition.implementation.kind, 'application');
  if (saved.definition.implementation.kind !== 'application') throw new Error('Expected application configuration');
  const config = structuredClone(saved.definition.implementation.config);
  assert.ok(isRecord(config.providers) && isRecord(config.providers.primary) && isRecord(config.providers.primary.credential));
  assert.ok(Array.isArray(config.connections) && isRecord(config.connections[0]) && isRecord(config.private));
  assert.match(String(config.connections[0].token), /^unifai-secret:v1:/);
  config.title = 'Completed client configuration';
  config.providers.primary.credential.endpoint = 'provider';
  config.connections[0].endpoint = 'connection';
  config.private.destination = 'destination';
  const complete = await saveProgram({ definition: { ...saved.definition, implementation: { ...saved.definition.implementation, config } }, expected_version: saved.version });
  const revision = await publishProgram(definition.program_id, complete.version);
  await startProgram({ execution_id: 'client-completed-configuration', program: { program_id: definition.program_id, revision: revision.revision }, inputs: {} });
  assert.deepEqual((await completed('client-completed-configuration')).result, { title: 'Completed client configuration', endpoint: 'connection' });
}

async function verifyOwnedBodies(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const operation = (await listResourcePage({ category: 'operations' })).resources.find(value => value.name === 'Client operation')!;
  assert.ok(operation.source);
  const body: ProgramBody = { input_schema: { type: 'object' }, output_schema: { type: 'object' }, execution_profile: null, implementation: {
    kind: 'graph', resources: [], steps: [{ kind: 'operation', uid: 'work', element: operation.source.key, execution: { profile: 'process' }, inputs: { text: { kind: 'path', path: ['input', 'name'] } }, outputs: { values: { kind: 'path', path: [] } }, max_attempts: 1, metadata: {} }],
    edges: {}, conditions: [], entry: 'work', exit: 'work', environments: {}, recursion_limit: 100,
    inputs: {}, outputs: { answer: { kind: 'path', path: ['values', 'text'] } },
  } };
  const definition: ProgramDefinition = { ...base, program_id: 'client-owned', name: 'Owned composition', implementation: {
    kind: 'application', implementation: 'map', version: '1', config: { concurrency: 2, max_items: 3, inputs: { name: { kind: 'path', path: ['item'] } } },
    children: { body }, environments: {}, child_environment_imports: {},
  } };
  const before = (await listPrograms()).programs.length;
  const saved = await saveProgram({ definition, expected_version: 0, resource_selections: [{ source: operation.source, adoption: 'reject', body_path: ['body'] }] });
  assert.deepEqual((await getProgramDraft(definition.program_id)), saved);
  assert.equal((await listPrograms()).programs.length, before + 1);
  assert.ok((await validateProgramDraft(definition.program_id, saved.version)).valid);
  const published = await publishProgram(definition.program_id, saved.version);
  const reference = { program_id: definition.program_id, revision: published.revision };
  assert.deepEqual(await getProgramRevision(reference), published);
  await startProgram({ execution_id: 'client-owned-run', program: reference, inputs: { items: ['one', 'two'] } });
  const result = await completed('client-owned-run');
  assert.equal(result.content_digest, published.content_digest);
  assert.deepEqual(result.body_path, []);
  assert.deepEqual((result.result as { items: { value: { answer: string } }[] }).items.map(item => item.value.answer), ['changed:client-middle:one', 'changed:client-middle:two']);
  const children = await listProgramExecutionChildren(result.execution_id);
  assert.equal(children.length, 2);
  assert.equal(new Set(children.map(child => child.execution_id)).size, 2);
  for (const child of children) {
    assert.deepEqual(child.program, reference);
    assert.deepEqual(child.body_path, ['body']);
    assert.equal(child.content_digest, published.content_digest);
    assert.equal(child.parent_execution_id, result.execution_id);
  }
}

async function verifySavedResources(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const coding = await createResource({ category: 'operations', type: 'codex_coding', name: 'Numeric snapshot', config: { model: 'capture-only', timeout_seconds: 120 } });
  assert.ok(coding.source);
  const snapshot = await captureResourceSnapshot(coding.source);
  assert.equal(snapshot.schema_version, 2);
  const numeric: ProgramDefinition = { ...base, program_id: 'numeric-snapshot', name: 'Numeric snapshot', implementation: {
    kind: 'application', implementation: 'placed_operation', version: '1', config: { bundle: snapshot as unknown as JsonValue, execution: { profile: 'process' } }, children: {}, environments: {}, child_environment_imports: {},
  } };
  const numericDraft = await saveProgram({ definition: numeric, expected_version: 0 });
  assert.ok(numericDraft.definition.implementation.kind === 'application');
  const retainedBundle = numericDraft.definition.implementation.config.bundle;
  assert.ok(isRecord(retainedBundle));
  assert.equal(retainedBundle.content_digest, snapshot.content_digest);
  const revisionWithNumbers = await publishProgram(numeric.program_id, numericDraft.version);
  assert.equal(revisionWithNumbers.definition.program_id, numeric.program_id);
  const changedSnapshot = structuredClone(snapshot);
  changedSnapshot.entries[0].resource.config.timeout_seconds = 121;
  assert.ok(numeric.implementation.kind === 'application');
  numeric.implementation.config.bundle = changedSnapshot as unknown as JsonValue;
  await assert.rejects(saveProgram({ definition: numeric, expected_version: numericDraft.version }));
  const leaf = await createResource({ category: 'tools', type: 'platform_dependency', name: 'Client leaf', config: {} });
  const middle = await createResource({ category: 'tools', type: 'platform_dependency', name: 'Client middle', config: { value: 'client-middle', dependency: '$ref:' + leaf.rid } });
  const root = await createResource({ category: 'operations', type: 'platform_text_operation', name: 'Client operation', config: { dependency: '$ref:' + middle.rid }, execution: { profile: 'process' } });
  const page = await listResourcePage({ category: 'operations', limit: 1 });
  const selected = page.resources.find(value => value.rid === root.rid)!;
  assert.ok(selected.source);
  const contracts = await catalogService.fetchElementContracts('operations', root.type);
  assert.deepEqual(Object.keys(contracts).sort(), ['input_schema', 'output_schema']);
  assert.deepEqual(contracts.input_schema?.required, ['text']);
  const definition: ProgramDefinition = { ...base, program_id: 'saved-operation', name: 'Saved operation', implementation: {
    kind: 'graph', resources: [], steps: [{ kind: 'operation', uid: 'work', element: selected.source.key, execution: { profile: selected.execution?.profile }, inputs: { text: { kind: 'path', path: ['input', 'name'] } }, outputs: { values: { kind: 'path', path: [] } }, max_attempts: 1, metadata: {} }],
    edges: {}, conditions: [], entry: 'work', exit: 'work', environments: {}, recursion_limit: 100,
    inputs: {}, outputs: { answer: { kind: 'path', path: ['values', 'text'] } },
  } };
  const draft = await saveProgram({ definition, expected_version: 0, resource_selections: [{ source: selected.source, adoption: 'reject' }] });
  assert.ok(draft.definition.implementation.kind === 'graph');
  assert.equal(draft.definition.implementation.resources.length, 3);
  const revision = await publishProgram(definition.program_id, draft.version);
  const pin = { program_id: definition.program_id, revision: revision.revision };
  await updateResource({ resourceId: root.rid, config: { ...root.cfg_dict, prefix: 'changed:' }, expected_version: root.version });
  await startProgram({ execution_id: 'saved-op-original', program: pin, inputs: { name: 'original' } });
  assert.deepEqual((await completed('saved-op-original')).result, { answer: 'typed:client-middle:original' });
  const changed = (await listResourcePage({ category: 'operations' })).resources.find(value => value.rid === root.rid)!;
  assert.ok(changed.source && changed.source.revision !== selected.source.revision);
  await assert.rejects(saveProgram({ definition: draft.definition, expected_version: draft.version, resource_selections: [{ source: changed.source, adoption: 'reject' }] }), error =>
    !!error && typeof error === 'object' && 'response' in error && (error.response as { status: number }).status === 409);
  const adopted = await saveProgram({ definition: draft.definition, expected_version: draft.version, resource_selections: [{ source: changed.source, adoption: 'replace' }] });
  const newer = await publishProgram(definition.program_id, adopted.version);
  await startProgram({ execution_id: 'saved-op-adopted', program: { program_id: definition.program_id, revision: newer.revision }, inputs: { name: 'adopted' } });
  assert.deepEqual((await completed('saved-op-adopted')).result, { answer: 'changed:client-middle:adopted' });
}

async function verifySavedCondition(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const root = (await listResourcePage({ category: 'operations' })).resources.find(value => value.name === 'Client operation')!;
  assert.ok(root.source);
  const condition = await createResource({ category: 'conditions', type: 'threshold', name: 'Client threshold', config: { input_path: ['output'], threshold: 0.5 }, execution: { profile: 'process' } });
  assert.ok(condition.source);
  const metadata = await catalogService.fetchElementContracts('conditions', condition.type);
  assert.deepEqual(metadata.output_schema?.symbolic_branches && (metadata.output_schema.symbolic_branches as { name: boolean }[]).map(value => value.name), [true, false]);
  const number: ProgramDefinition = { ...base, program_id: 'client-number', name: 'Number input', implementation: { kind: 'application', implementation: 'greeting', version: '1', config: { prefix: '' }, children: {}, environments: {}, child_environment_imports: {} } };
  const savedNumber = await saveProgram({ definition: number, expected_version: 0 });
  const numberRevision = await publishProgram(number.program_id, savedNumber.version);
  const pin = { program_id: number.program_id, revision: numberRevision.revision };
  const graph: Extract<ProgramDefinition['implementation'], { kind: 'graph' }> = {
    kind: 'graph', resources: [], steps: [
      { kind: 'program', uid: 'score', program: pin, inputs: { name: { kind: 'path', path: ['user_prompt'] } }, outputs: { output: { kind: 'path', path: ['answer'] } }, environment_imports: {}, max_attempts: 1, metadata: {} },
      ...['yes', 'no'].map(uid => ({ kind: 'operation' as const, uid, element: root.source!.key, execution: { profile: 'process' }, inputs: { text: { kind: 'literal' as const, value: uid } }, outputs: { values: { kind: 'path' as const, path: [] } }, max_attempts: 1, metadata: {} })),
      { kind: 'program', uid: 'finish', program: pin, inputs: { name: { kind: 'literal', value: 'done' } }, outputs: {}, environment_imports: {}, max_attempts: 1, metadata: {} },
    ], write_policy: 'reduce', edges: { score: ['no'], yes: ['finish'], no: ['finish'] }, conditions: [{ source: 'score', condition: condition.source.key, branches: { true: 'yes', false: 'no' }, execution: { profile: 'process' } }],
    entry: 'score', exit: 'finish', inputs: { user_prompt: { kind: 'path', path: ['name'] } }, outputs: { answer: { kind: 'path', path: ['values', 'text'] }, selected: { kind: 'path', path: ['values', 'key'] } }, environments: {}, recursion_limit: 100,
  };
  const definition: ProgramDefinition = { ...base, program_id: 'client-routing', name: 'Routed operations', implementation: graph };
  const mixed = await saveProgram({ definition, expected_version: 0, resource_selections: [{ source: root.source, adoption: 'reject' }, { source: condition.source, adoption: 'reject' }] });
  const report = await validateProgramDraft(definition.program_id, mixed.version);
  assert.equal(report.valid, false);
  assert.equal(report.issues[0].code, 'INVALID_TOPOLOGY');
  await assert.rejects(publishProgram(definition.program_id, mixed.version));
  assert.ok(mixed.definition.implementation.kind === 'graph');
  const correctedGraph = removeGraphEdges(mixed.definition.implementation, new Set([orderingEdgeId('score', 'no')]));
  const ordered = await saveProgram({ definition: { ...mixed.definition, implementation: { ...correctedGraph, write_policy: 'ordered' } }, expected_version: mixed.version });
  const writers = await validateProgramDraft(definition.program_id, ordered.version);
  assert.equal(writers.valid, false);
  assert.equal(writers.issues[0].code, 'INVALID_BINDING');
  await assert.rejects(publishProgram(definition.program_id, ordered.version));
  const saved = await saveProgram({ definition: { ...ordered.definition, implementation: { ...correctedGraph, write_policy: 'reduce' } }, expected_version: ordered.version });
  const revision = await publishProgram(definition.program_id, saved.version);
  assert.deepEqual((await getProgramDraft(definition.program_id)).definition, saved.definition);
  for (const [name, selected] of [['0.75', 'yes'], ['0.25', 'no']]) {
    const id = 'client-route-' + selected;
    await startProgram({ execution_id: id, program: { program_id: definition.program_id, revision: revision.revision }, inputs: { name } });
    assert.deepEqual((await completed(id)).result, { answer: 'changed:client-middle:' + selected, selected });
  }
}

async function verifyUnfinishedDraft(base: Pick<ProgramDefinition, 'owner' | 'input_schema' | 'output_schema' | 'execution_profile'>) {
  const definition: ProgramDefinition = { ...base, program_id: 'client-unfinished', name: 'Unfinished work', implementation: { kind: 'graph', steps: [], resources: [], edges: {}, conditions: [], entry: '', exit: '', inputs: {}, outputs: {}, environments: {}, recursion_limit: 100 } };
  const draft = await saveProgram({ definition, expected_version: 0 });
  assert.deepEqual(await getProgramDraft(definition.program_id), draft);
  const report = await validateProgramDraft(definition.program_id, draft.version);
  assert.equal(report.valid, false);
  assert.equal(report.version, draft.version);
  assert.equal(report.issues[0].code, 'INVALID_TOPOLOGY');
  assert.deepEqual(report.issues[0].path, ['implementation']);
  await assert.rejects(publishProgram(definition.program_id, draft.version));
  assert.deepEqual((await listProgramRevisions(definition.program_id)).revisions, []);
  const updated = await saveProgram({ definition: { ...definition, implementation: { kind: 'application', implementation: 'greeting', version: '1', config: {}, children: {}, environments: {}, child_environment_imports: {} } }, expected_version: draft.version });
  assert.deepEqual(await validateProgramDraft(definition.program_id, updated.version), { version: updated.version, valid: true, issues: [] });
  await assert.rejects(validateProgramDraft(definition.program_id, draft.version));
  const published = await publishProgram(definition.program_id, updated.version);
  await startProgram({ execution_id: 'client-completed-draft', program: { program_id: definition.program_id, revision: published.revision }, inputs: { name: 'completed' } });
  assert.deepEqual((await completed('client-completed-draft')).result, { answer: 'hello completed' });
}

export default async function verifyComposition() {
  assert.ok(process.env.UNIFAI_TEST_UI_API_URL);
  api.defaults.baseURL = process.env.UNIFAI_TEST_UI_API_URL;
  assert.deepEqual(await catalogService.fetchExecutionProfiles(), { profiles: ['process', 'thread'], default_profile: 'thread', environment_profiles: [] });
  const catalog = await programImplementations();
  for (const key of ['map', 'repeat', 'choose', 'wait']) assert.ok(catalog.some(value => value.key === key && value.version === '1'));
  assert.ok(!JSON.stringify(catalog).includes('execution_profiles'));
  const mapped = catalog.find(value => value.key === 'map')!;
  const owner = { type: 'user' as const, id: 'owner', display_name: 'owner' };
  const base = { owner, input_schema: { type: 'object' }, output_schema: { type: 'object' }, execution_profile: null };
  const body: ProgramDefinition = { ...base, program_id: 'client-body', name: 'Client child', implementation: { kind: 'application', implementation: 'greeting', version: '1', config: { prefix: 'client:' }, children: {}, environments: {}, child_environment_imports: {} } };
  const bodyDraft = await saveProgram({ definition: body, expected_version: 0, presentation: { positions: { greeting: { x: 10, y: 20 } } } });
  const publishedBody = await publishProgram(body.program_id, bodyDraft.version);
  const reference = { program_id: body.program_id, revision: publishedBody.revision };
  assert.equal((await getProgramRevision(reference)).definition.name, body.name);
  const definition: ProgramDefinition = { ...base, program_id: 'client-map', name: 'Client map', input_schema: mapped.input_schema!, output_schema: mapped.output_schema!, implementation: { kind: 'application', implementation: 'map', version: '1', config: { concurrency: 2, max_items: 10, inputs: { name: { kind: 'path', path: ['item'] } } }, children: { body: reference }, environments: {}, child_environment_imports: {} } };
  const draft = await saveProgram({ definition, expected_version: 0 });
  const published = await publishProgram(definition.program_id, draft.version);
  assert.deepEqual(await getProgramDraft(body.program_id), bodyDraft);
  assert.deepEqual((await listPrograms()).programs.map(value => value.program_id), ['client-body', 'client-map']);
  const edited = await saveProgram({ definition: { ...bodyDraft.definition, name: 'Edited child' }, expected_version: bodyDraft.version });
  assert.equal(edited.version, bodyDraft.version + 1);
  assert.deepEqual(edited.presentation, bodyDraft.presentation);
  assert.equal((await publishProgram(body.program_id, bodyDraft.version)).revision, publishedBody.revision);
  const newer = await publishProgram(body.program_id, edited.version);
  assert.deepEqual((await listProgramRevisions(body.program_id)).revisions.map(value => value.program.revision), [newer.revision, publishedBody.revision]);
  assert.equal((await getProgramRevision(reference)).definition.name, 'Client child');
  await assert.rejects(saveProgram({ definition: body, expected_version: bodyDraft.version }), error =>
    !!error && typeof error === 'object' && 'response' in error && (error.response as { status: number }).status === 409);
  const intent = { execution_id: 'client-composition-run', program: { program_id: definition.program_id, revision: published.revision }, inputs: { items: ['one', 'two'] } };
  assert.equal((await startProgram(intent)).execution_id, intent.execution_id);
  let execution = await inspectProgramExecution(intent.execution_id);
  const deadline = Date.now() + 20_000;
  while (!['completed', 'failed', 'cancelled'].includes(execution.phase) && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 20));
    execution = await inspectProgramExecution(intent.execution_id);
  }
  assert.equal(execution.phase, 'completed');
  assert.deepEqual((execution.result as { items: { value: { answer: string } }[] }).items.map(value => value.value.answer), ['client:one', 'client:two']);
  assert.equal((await startProgram(intent)).execution_id, execution.execution_id);
  const wait: ProgramDefinition = { ...body, program_id: 'client-wait', name: 'Wait', implementation: { ...body.implementation as Extract<ProgramDefinition['implementation'], { kind: 'application' }>, implementation: 'wait', config: { channel: 'never', timeout_seconds: 60 } } };
  const waitDraft = await saveProgram({ definition: wait, expected_version: 0 }); const waiting = await publishProgram(wait.program_id, waitDraft.version);
  await startProgram({ execution_id: 'client-wait-run', program: { program_id: wait.program_id, revision: waiting.revision }, inputs: {} });
  await cancelProgramExecution('client-wait-run');
  let cancelled = await inspectProgramExecution('client-wait-run');
  while (!['completed', 'failed', 'cancelled'].includes(cancelled.phase) && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 20)); cancelled = await inspectProgramExecution('client-wait-run');
  }
  assert.equal(cancelled.phase, 'cancelled');
  await verifySavedResources(base);
  await verifySavedCondition(base);
  await verifyUnfinishedDraft(base);
  await verifyOwnedBodies(base);
  await verifyIncompleteConfiguration(base);
  await verifyBindingReadiness();
  await verifyInstalledProgramModels(base);
  await verifyWholeValueBindings(base);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(programImplementations(controller.signal));
  console.log('Program composition clients passed against native FastAPI');
}
