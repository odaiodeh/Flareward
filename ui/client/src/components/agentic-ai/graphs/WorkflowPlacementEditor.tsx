import { useEffect, useId, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useExecutionProfiles } from '@/hooks/use-execution-profiles';
import type { ExecutionSelection, WorkflowPlacement, YamlFlowState } from '@/types/graph';
import { applyWorkflowPlacement } from '@/lib/workflow-placement';
import { previewBlueprintPlacement } from '@/api/blueprints';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const selectClass = 'w-full rounded-md border border-input bg-background px-3 py-2 text-sm';

function PlacementSelect({ value, onChange, profiles, environments, disabled, label }: {
  value?: ExecutionSelection | null;
  onChange: (value: ExecutionSelection | null) => void;
  profiles: string[];
  environments: string[];
  disabled: boolean;
  label: string;
}) {
  const selected = value?.environment ? `environment:${value.environment}`
    : value?.profile ? `profile:${value.profile}` : value == null ? 'inherit' : 'default';
  const choices = ['inherit', 'default', ...profiles.map(name => `profile:${name}`),
    ...environments.map(name => `environment:${name}`)];
  return (
    <select aria-label={label} value={selected} disabled={disabled} className={selectClass}
      onChange={event => {
        const option = event.target.value;
        onChange(option === 'inherit' ? null : option === 'default' ? {}
          : option.startsWith('profile:') ? { profile: option.slice(8) }
          : { environment: option.slice(12) });
      }}>
      <option value="inherit">Inherit element preference</option>
      <option value="default">Use workflow default</option>
      {!choices.includes(selected) && <option value={selected} disabled>{selected} (unavailable)</option>}
      {profiles.map(name => <option key={`profile:${name}`} value={`profile:${name}`}>Profile: {name}</option>)}
      {environments.map(name => <option key={`environment:${name}`} value={`environment:${name}`}>Shared: {name}</option>)}
    </select>
  );
}

export function WorkflowPlacementEditor({ flow, value, onChange, teamId, disabled = false }: {
  flow: YamlFlowState;
  value: WorkflowPlacement;
  onChange: (value: WorkflowPlacement) => void;
  disabled?: boolean;
  teamId?: string;
}) {
  const previewId = useId();
  const { data, isError, isPending } = useExecutionProfiles(teamId);
  const [environmentName, setEnvironmentName] = useState('');
  const [environmentProfile, setEnvironmentProfile] = useState('');
  const profiles = data?.profiles ?? [];
  const environmentProfiles = data?.environment_profiles ?? [];
  const locked = disabled || isPending || isError;
  const name = environmentName.trim();
  const nameTaken = Object.hasOwn(value.environments, name);
  const draft = useMemo(() => applyWorkflowPlacement(flow, value), [flow, value]);
  const [settled, setSettled] = useState<{ draft: YamlFlowState; version: number } | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(previous => ({ draft, version: (previous?.version ?? 0) + 1 })), 300);
    return () => window.clearTimeout(timer);
  }, [draft]);
  const preview = useQuery({
    queryKey: ['blueprint-placement', teamId, previewId, settled?.version],
    queryFn: ({ signal }) => previewBlueprintPlacement(draft, teamId, signal),
    enabled: settled?.draft === draft && flow.plan.length > 0,
    retry: false,
    gcTime: 0,
  });
  const verified = settled?.draft === draft && !preview.isFetching && !preview.isError ? preview.data : undefined;
  const updateStep = (uid: string, field: 'execution' | 'condition_execution', selection: ExecutionSelection | null) =>
    onChange({ ...value, steps: { ...value.steps, [uid]: { ...value.steps[uid], [field]: selection } } });

  return (
    <section className="space-y-4 border-t border-gray-700 pt-4" aria-label="Workflow execution settings">
      <h3 className="font-medium">Execution settings</h3>
      {isError && <p role="alert" className="text-sm text-destructive">Could not load approved profiles. Saved choices are preserved.</p>}
      <label className="block space-y-2 text-sm">
        <span>Workflow default</span>
        <select aria-label="Workflow default" className={selectClass} value={value.execution_profile ?? ''}
          disabled={locked} onChange={event => onChange({ ...value, execution_profile: event.target.value || null })}>
          <option value="">Platform default{data ? ` (${data.default_profile})` : ''}</option>
          {value.execution_profile && !profiles.includes(value.execution_profile)
            && <option value={value.execution_profile} disabled>{value.execution_profile} (saved/unavailable)</option>}
          {profiles.map(profile => <option key={profile}>{profile}</option>)}
        </select>
      </label>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Shared environments</legend>
        <p className="text-xs text-muted-foreground">Steps using the same name reuse its environment within one run. Run Engine releases owned environments after the run; a later chat turn gets a new run.</p>
        {Object.entries(value.environments).map(([alias, profile]) => {
          const used = Object.values(value.steps).some(step =>
            step.execution?.environment === alias || step.condition_execution?.environment === alias);
          return (
            <div key={alias} className="flex items-center gap-2 text-sm">
              <span className="min-w-0 flex-1 break-all">{alias}: {profile}</span>
              <Button type="button" variant="outline" disabled={disabled || used}
                title={used ? 'Change the steps using this environment first' : 'Remove environment'}
                onClick={() => {
                  const { [alias]: removed, ...remaining } = value.environments;
                  onChange({ ...value, environments: remaining });
                }}>Remove</Button>
            </div>
          );
        })}
        <div className="flex gap-2">
          <Input aria-label="Shared environment name" placeholder="e.g. coding-workspace" value={environmentName}
            disabled={locked} onChange={event => setEnvironmentName(event.target.value)} />
          <select aria-label="Shared environment profile" className={selectClass} value={environmentProfile}
            disabled={locked} onChange={event => setEnvironmentProfile(event.target.value)}>
            <option value="">Select profile</option>
            {environmentProfiles.map(profile => <option key={profile}>{profile}</option>)}
          </select>
          <Button type="button" disabled={locked || !name || nameTaken || !environmentProfiles.includes(environmentProfile)}
            onClick={() => {
              onChange({ ...value, environments: { ...value.environments, [name]: environmentProfile } });
              setEnvironmentName('');
            }}>Add</Button>
        </div>
        {nameTaken && <p role="alert" className="text-xs text-destructive">This environment name already exists.</p>}
        {data && !environmentProfiles.length && <p className="text-xs text-muted-foreground">No configured profiles support shared environments.</p>}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Step placement preview</legend>
        {preview.isError && settled?.draft === draft && <p role="alert" className="text-sm text-destructive">
          Placement validation failed. Check this workflow's resources, profiles and environment selections.
        </p>}
        {flow.plan.flatMap(step => [
          { uid: step.uid, field: 'execution' as const, reference: step.node, category: 'nodes' as const, label: step.uid },
          ...(step.exit_condition ? [{ uid: step.uid, field: 'condition_execution' as const,
            reference: step.exit_condition, category: 'conditions' as const, label: `${step.uid} condition` }] : []),
        ]).map(item => {
          const selection = value.steps[item.uid]?.[item.field];
          const effective = verified?.invocations.find(invocation =>
            invocation.step_uid === item.uid && invocation.category === item.category);
          return (
            <div key={`${item.uid}:${item.field}`} className="space-y-1">
              <span className="text-sm font-medium">{item.label}</span>
              <PlacementSelect label={`${item.label} placement`} value={selection}
                profiles={profiles} environments={Object.keys(value.environments)} disabled={locked}
                onChange={selection => updateStep(item.uid, item.field, selection)} />
              <p className="text-xs text-muted-foreground">{effective
                ? `Validated profile: ${effective.profile}${effective.environment ? ` · Shared: ${effective.environment} · Bound to this run` : ' · Invocation binding'}`
                : 'Placement not yet validated for these settings.'}</p>
            </div>
          );
        })}
        <p className="text-xs text-muted-foreground">Overrides apply only to this workflow. The server resolves saved element preferences and validates placement without running the graph. Execution prepares its own snapshot and validates again.</p>
      </fieldset>
    </section>
  );
}
