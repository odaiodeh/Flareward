import type { WorkflowPlacement, YamlFlowState } from '@/types/graph';

export function workflowPlacement(flow: YamlFlowState): WorkflowPlacement {
  return {
    execution_profile: flow.execution_profile ?? null,
    environments: { ...flow.environments },
    steps: Object.fromEntries(flow.plan.map(step => [step.uid, {
      execution: step.execution, condition_execution: step.condition_execution,
    }])),
  };
}

export function applyWorkflowPlacement(flow: YamlFlowState, placement: WorkflowPlacement): YamlFlowState {
  return {
    ...flow,
    execution_profile: placement.execution_profile,
    environments: { ...placement.environments },
    plan: flow.plan.map(step => ({ ...step, ...placement.steps[step.uid] })),
  };
}

