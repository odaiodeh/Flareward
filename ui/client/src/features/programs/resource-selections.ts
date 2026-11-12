import type { CustomCoordinatorDefinition, GraphDefinition, GraphStep, ProgramTarget, ResourceSelection } from '@/api/programs';
import type { JsonValue } from '@shared/json';
import { isRecord } from '@/lib/json';

/** Preview identity is local editor state, never part of the save command. */
export type PendingResourceSelection = ResourceSelection & { capturedDigest?: string };

export function configurationPath(pointer: string, config: JsonValue): (string | number)[] {
  let current: JsonValue | undefined = config;
  return pointer ? pointer.slice(1).split('/').map(token => {
    const name = token.replace(/~1/g, '/').replace(/~0/g, '~');
    const part = Array.isArray(current) ? Number(name) : name;
    current = Array.isArray(current) && typeof part === 'number' ? current[part] : isRecord(current) ? current[name] as JsonValue : undefined;
    return part;
  }) : [];
}

export function queueResourceSelection(previous: PendingResourceSelection[], selected: PendingResourceSelection): PendingResourceSelection[] {
  const destination = (value: PendingResourceSelection) => JSON.stringify([
    value.body_path ?? [], value.configuration_path ?? [value.source.key.category, value.source.key.rid],
    value.configuration_path != null ? 'configuration' : 'graph',
  ]);
  return [...previous.filter(value => destination(value) !== destination(selected)), selected];
}

export function activeResourceSelections(implementation: GraphDefinition | CustomCoordinatorDefinition, selections: PendingResourceSelection[]): PendingResourceSelection[] {
  const key = (resource: { category: string; rid: string }) => JSON.stringify([resource.category, resource.rid]);
  return selections.filter(selection => {
    let scope: GraphDefinition | CustomCoordinatorDefinition = implementation;
    for (const name of selection.body_path ?? []) {
      const step: GraphStep | undefined = scope.kind === 'graph' ? scope.steps.find(step => step.uid === name) : undefined;
      const target: ProgramTarget | undefined = scope.kind === 'application' ? scope.children[name] : step?.kind === 'program' ? step.program : undefined;
      if (!target || 'program_id' in target) return false;
      scope = target.implementation;
    }
    if (selection.configuration_path != null) {
      if (scope.kind !== 'application') return false;
      let bundle: JsonValue | undefined = scope.config;
      for (const part of selection.configuration_path) bundle = Array.isArray(bundle) && typeof part === 'number' ? bundle[part] : isRecord(bundle) && typeof part === 'string' ? bundle[part] as JsonValue : undefined;
      return isRecord(bundle) && isRecord(bundle.root) && bundle.root.category === selection.source.key.category && bundle.root.rid === selection.source.key.rid
        && (selection.capturedDigest === undefined || bundle.content_digest === selection.capturedDigest);
    }
    if (scope.kind !== 'graph') return false;
    return scope.steps.some(step => step.kind !== 'program' && key(step.element) === key(selection.source.key))
      || scope.conditions.some(route => route.kind === 'condition' && key(route.condition) === key(selection.source.key));
  });
}

