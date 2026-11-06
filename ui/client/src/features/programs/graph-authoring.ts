import type { ApplicationDefinition, GraphDefinition, GraphStep, ProgramTarget, ResourceSelection } from '@/api/programs';
import type { JsonObject } from '@shared/json';
import { isRecord } from '@/lib/json';

export const orderingEdgeId = (source: string, target: string) => JSON.stringify([source, target]);
export const branchEdgeId = (source: string, label: string, target: string) => JSON.stringify([source, label, target]);

/** Delete only the selected edge identities, including individual labels sharing a target. */
export function removeGraphEdges(graph: GraphDefinition, removed: ReadonlySet<string>): GraphDefinition {
  return {
    ...graph,
    edges: Object.fromEntries(Object.entries(graph.edges).map(([source, targets]) => [source, targets.filter(target => !removed.has(orderingEdgeId(source, target)))])),
    conditions: graph.conditions.flatMap(route => {
      const branches = Object.fromEntries(Object.entries(route.branches).filter(([label, target]) => !removed.has(branchEdgeId(route.source, label, target))));
      return Object.keys(branches).length ? [{ ...route, branches }] : [];
    }),
  };
}

/** Removing a block does not invent replacement ordering or silently redirect a branch. */
export function removeGraphStep(graph: GraphDefinition, uid: string): GraphDefinition {
  return {
    ...graph, steps: graph.steps.filter(step => step.uid !== uid),
    edges: Object.fromEntries(Object.entries(graph.edges).filter(([source]) => source !== uid).map(([source, targets]) => [source, targets.filter(target => target !== uid)])),
    conditions: graph.conditions.flatMap(route => {
      if (route.source === uid) return [];
      const branches = Object.fromEntries(Object.entries(route.branches).filter(([, target]) => target !== uid));
      return Object.keys(branches).length ? [{ ...route, branches }] : [];
    }),
    entry: graph.entry === uid ? '' : graph.entry,
    exit: graph.exit === uid ? '' : graph.exit,
  };
}

export function activeResourceSelections(graph: GraphDefinition, selections: ResourceSelection[]): ResourceSelection[] {
  const key = (resource: { category: string; rid: string }) => JSON.stringify([resource.category, resource.rid]);
  return selections.filter(selection => {
    let scope: GraphDefinition | ApplicationDefinition = graph;
    for (const name of selection.body_path ?? []) {
      const step: GraphStep | undefined = scope.kind === 'graph' ? scope.steps.find(step => step.uid === name) : undefined;
      const target: ProgramTarget | undefined = scope.kind === 'application' ? scope.children[name] : step?.kind === 'program' ? step.program : undefined;
      if (!target || 'program_id' in target) return false;
      scope = target.implementation;
    }
    if (scope.kind !== 'graph') return false;
    return scope.steps.some(step => step.kind !== 'program' && key(step.element) === key(selection.source.key))
      || scope.conditions.some(route => key(route.condition) === key(selection.source.key));
  });
}

/** Condition metadata uses native boolean names; routing contracts use normalized labels. */
export function conditionLabels(schema: JsonObject | null): { value: string; label: string }[] {
  if (!schema || !Array.isArray(schema.symbolic_branches)) return [];
  return schema.symbolic_branches.flatMap(branch => {
    if (!isRecord(branch) || !['string', 'number', 'boolean'].includes(typeof branch.name)) return [];
    return [{ value: String(branch.name), label: typeof branch.display_name === 'string' ? branch.display_name : String(branch.name) }];
  });
}
