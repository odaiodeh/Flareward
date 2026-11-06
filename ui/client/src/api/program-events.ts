import api from '@/http/axiosAgentConfig';
import type { JsonValue } from '@shared/json';
import type { ProgramDefinition, ProgramExecution, ProgramRef, WorkflowAccess } from './programs';

export interface CreateEventSource {
  name: string; program: ProgramRef; event_type: string; expires_at: string;
  input_schema?: Record<string, JsonValue>; workflow_access?: WorkflowAccess[];
}
export interface ProgramEventSource extends CreateEventSource {
  source_id: string; owner: ProgramDefinition['owner']; approved_by: ProgramDefinition['owner'];
  approved_at: string; prepared_sha256: string; revoked: boolean;
  input_schema: Record<string, JsonValue>; workflow_access: WorkflowAccess[];
}
export interface ProgramEvent { event_id: string; event_type: string; inputs: JsonValue }
export interface PreparedProgramPlacement {
  program: ProgramRef; body_path: string[]; default_profile: string;
  environments: Record<string, string>; imported_environments: string[];
  invocations: { step_uid: string; category: 'nodes' | 'conditions' | 'operations'; profile: string | null; environment: string | null }[];
  children: Record<string, { environment_imports: Record<string, string>; program: PreparedProgramPlacement }>;
  dynamic_invocations: boolean;
}
export interface EventSourceSettings {
  work_limits: ProgramExecution['work_limits']; admitted_profiles: ProgramExecution['admitted_profiles'];
  placement: PreparedProgramPlacement | null;
  credential_revision: number;
}
export interface EventAdmission {
  source_id: string; event_id: string; execution_id: string;
  submission: 'prepared' | 'starting' | 'accepted' | 'unconfirmed' | 'refused';
}
export async function createProgramEventSource(request: CreateEventSource, teamId?: string, signal?: AbortSignal): Promise<{ source: ProgramEventSource; credential: string }> {
  return (await api.post<{ source: ProgramEventSource; credential: string }>('/program-events/sources', request, { params: { teamId }, signal })).data;
}
export async function getProgramEventSource(id: string, teamId?: string, signal?: AbortSignal): Promise<ProgramEventSource> {
  return (await api.get<ProgramEventSource>(`/program-events/sources/${encodeURIComponent(id)}`, { params: { teamId }, signal })).data;
}
export async function getProgramEventSourceSettings(id: string, teamId?: string, signal?: AbortSignal): Promise<EventSourceSettings> {
  return (await api.get<EventSourceSettings>(`/program-events/sources/${encodeURIComponent(id)}/settings`, { params: { teamId }, signal })).data;
}
export async function rotateProgramEventCredential(id: string, expectedRevision: number, teamId?: string, signal?: AbortSignal): Promise<{ credential: string; revision: number }> {
  return (await api.post<{ credential: string; revision: number }>(`/program-events/sources/${encodeURIComponent(id)}/credential`, { expected_revision: expectedRevision }, { params: { teamId }, signal })).data;
}
export async function listProgramEventSources(after = '', teamId?: string, signal?: AbortSignal): Promise<ProgramEventSource[]> {
  return (await api.get<ProgramEventSource[]>('/program-events/sources', { params: { after, teamId }, signal })).data;
}
export async function revokeProgramEventSource(id: string, teamId?: string, signal?: AbortSignal): Promise<void> {
  await api.delete(`/program-events/sources/${encodeURIComponent(id)}`, { params: { teamId }, signal });
}
export async function deliverProgramEvent(credential: string, event: ProgramEvent, signal?: AbortSignal): Promise<EventAdmission> {
  return (await api.post<EventAdmission>('/program-events/deliveries', event, { headers: { Authorization: `Bearer ${credential}` }, signal })).data;
}
