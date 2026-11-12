import assert from 'node:assert/strict';
import { emptyGraphDefinition } from '../client/src/features/programs/authoring';
import type { CustomCoordinatorDefinition, GraphDefinition, ResourceSelection } from '../client/src/api/programs';
import { branchEdgeId, conditionLabels, orderingEdgeId, removeGraphEdges, removeGraphStep } from '../client/src/features/programs/graph-authoring';

import { activeResourceSelections, configurationPath, queueResourceSelection, type PendingResourceSelection } from '../client/src/features/programs/resource-selections';

export function verifyProgramGraphEditing() {
  const fresh = emptyGraphDefinition();
  assert.equal(fresh.kind, 'graph');
  fresh.edges.start = ['finish'];
  assert.deepEqual(emptyGraphDefinition().edges, {});
  const graph: GraphDefinition = {
    kind: 'graph', steps: ['start', 'yes', 'no', 'finish'].map(uid => ({ kind: 'operation', uid, element: { category: 'operations', rid: 'work' }, metadata: {}, max_attempts: 1, execution: {}, inputs: {}, outputs: {} })),
    resources: [], edges: { start: ['yes'], yes: ['finish'], no: ['finish'] },
    conditions: [{ kind: 'condition', source: 'start', condition: { category: 'conditions', rid: 'route' }, branches: { true: 'yes', also: 'yes', false: 'no' }, execution: { profile: 'process' } }],
    entry: 'start', exit: 'finish', inputs: {}, outputs: {}, environments: {}, recursion_limit: 100,
  };
  const original = structuredClone(graph);
  const oneLabel = removeGraphEdges(graph, new Set([branchEdgeId('start', 'true', 'yes')]));
  assert.deepEqual(oneLabel.conditions[0].branches, { also: 'yes', false: 'no' });
  assert.deepEqual(oneLabel.edges.start, ['yes']);
  const ordinary = removeGraphEdges(graph, new Set([orderingEdgeId('start', 'yes')]));
  assert.deepEqual(ordinary.edges.start, []);
  assert.deepEqual(ordinary.conditions, graph.conditions);
  const removed = removeGraphStep(graph, 'yes');
  assert.deepEqual(removed.conditions[0].branches, { false: 'no' });
  assert.deepEqual(removed.edges.start, []);
  assert.ok(!Object.hasOwn(removed.edges, 'yes'));
  assert.equal(removed.entry, 'start');
  const noStart = removeGraphStep(graph, 'start');
  assert.equal(noStart.entry, '');
  assert.deepEqual(noStart.conditions, []);
  assert.equal(removeGraphStep(graph, 'finish').exit, '');
  assert.deepEqual(graph, original);

  const selections: ResourceSelection[] = ['work', 'route', 'unused'].map((rid, index) => ({ source: { key: { rid, category: index === 1 ? 'conditions' : 'operations' }, revision: 'a'.repeat(64) }, adoption: 'reject' }));
  assert.deepEqual(activeResourceSelections(graph, selections), selections.slice(0, 2));
  assert.deepEqual(activeResourceSelections(noStart, selections), selections.slice(0, 1));
  const resultGraph: GraphDefinition = { ...graph, conditions: [{ kind: 'result', source: 'start', selection: { kind: 'path', path: ['results', 'start', 'outcome'] }, branches: { approved: 'yes', rejected: 'no' }, execution: {} }] };
  assert.deepEqual(activeResourceSelections(resultGraph, selections), selections.slice(0, 1));
  const resultEdited = removeGraphEdges(resultGraph, new Set([branchEdgeId('start', 'rejected', 'no')]));
  assert.deepEqual(resultEdited.conditions, [{ ...resultGraph.conditions[0], branches: { approved: 'yes' } }]);
  assert.deepEqual(removeGraphStep(resultGraph, 'start').conditions, []);
  const nested: GraphDefinition = { ...graph, steps: [{
    kind: 'program', uid: 'control', max_attempts: 1, metadata: {}, inputs: {}, outputs: {}, environment_imports: {},
    program: { input_schema: {}, output_schema: {}, execution_profile: null, implementation: {
      kind: 'application', implementation: 'map', version: '1', config: {}, environments: {}, child_environment_imports: {}, children: {
        body: { input_schema: {}, output_schema: {}, execution_profile: null, implementation: graph },
        pinned: { program_id: 'external', revision: 1 },
      },
    } },
  }] };
  const scoped = { ...selections[0], body_path: ['control', 'body'] };
  assert.deepEqual(activeResourceSelections(nested, [selections[0], scoped, { ...scoped, body_path: ['control', 'pinned'] }]), [scoped]);
  assert.deepEqual(activeResourceSelections(removeGraphStep(nested, 'control'), [scoped]), []);
  assert.deepEqual(conditionLabels({ symbolic_branches: [{ name: true, display_name: 'Yes' }, { name: false, display_name: 'No' }, { name: 'ready' }, { name: {} }] }), [
    { value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }, { value: 'ready', label: 'ready' },
  ]);
  const bundle = { root: { ...selections[0].source.key }, content_digest: 'captured', entries: [] };
  const custom: CustomCoordinatorDefinition = { kind: 'application', implementation: 'custom', version: '1', config: { stages: [{ bundle }, { bundle: { ...bundle, content_digest: 'older' } }], 'a/b': { '~name': {} } }, children: {}, environments: {}, child_environment_imports: {} };
  const pending: PendingResourceSelection = { ...selections[0], configuration_path: ['stages', 0, 'bundle'], capturedDigest: bundle.content_digest };
  assert.deepEqual(configurationPath('/stages/0/bundle', custom.config), pending.configuration_path);
  assert.deepEqual(configurationPath('/a~1b/~0name', custom.config), ['a/b', '~name']);
  assert.deepEqual(activeResourceSelections(custom, [pending]), [pending]);
  const moved = { ...custom, config: { stages: [{ bundle: { ...bundle, content_digest: 'older' } }, { bundle }] } };
  assert.deepEqual(activeResourceSelections(moved, [pending]), []);
  assert.deepEqual(activeResourceSelections({ ...custom, config: { stages: [] } }, [pending]), []);
  const second = { ...pending, configuration_path: ['stages', 1, 'bundle'] };
  assert.equal(queueResourceSelection([pending], second).length, 2);
  assert.deepEqual(queueResourceSelection([pending], { ...pending, adoption: 'replace' }), [{ ...pending, adoption: 'replace' }]);
  assert.equal(queueResourceSelection([selections[0]], { ...selections[0], body_path: ['child'] }).length, 2);

}
