import type { GraphDefinition } from '@/api/programs';
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

/** Condition metadata uses native boolean names; routing contracts use normalized labels. */
export function conditionLabels(schema: JsonObject | null): { value: string; label: string }[] {
  if (!schema || !Array.isArray(schema.symbolic_branches)) return [];
  return schema.symbolic_branches.flatMap(branch => {
    if (!isRecord(branch) || !['string', 'number', 'boolean'].includes(typeof branch.name)) return [];
    return [{ value: String(branch.name), label: typeof branch.display_name === 'string' ? branch.display_name : String(branch.name) }];
  });
}
