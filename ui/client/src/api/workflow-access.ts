import api from '@/http/axiosAgentConfig';
import type { JsonObject } from '@shared/json';

export interface WorkflowAccessDescriptor {
  purpose: string; name: string; description: string; request_schema: JsonObject;
}

/** Authoring metadata only; this read cannot issue workflow credentials. */
export async function workflowAccessCatalog(teamId?: string, signal?: AbortSignal): Promise<WorkflowAccessDescriptor[]> {
  return (await api.get<WorkflowAccessDescriptor[]>('/catalog/workflow-access', { params: { teamId }, signal })).data;
}
