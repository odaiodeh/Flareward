import api from '@/http/axiosAgentConfig';
import type { JsonValue } from '@shared/json';
import type { ProgramBindings, ProgramDefinition, ProgramRef, WorkflowAccess } from './programs';

export interface WorkflowConsentRequest { requirements: WorkflowAccess[]; expires_at: string }
export interface WorkflowConsent extends WorkflowConsentRequest {
  consent_id: string; source_id: string; owner: ProgramDefinition['owner'];
  approved_by: { type: 'user'; id: string; display_name: string }; approved_at: string;
  definition_sha256: string; prepared_sha256: string; revoked: boolean;
}
export interface CreateProgramSchedule {
  session: { program: ProgramRef; interaction?: 'data' | 'conversation'; metadata?: Record<string, JsonValue>; input_bindings?: ProgramBindings; output_bindings?: ProgramBindings };
  inputs?: Record<string, JsonValue>; source?: 'manual' | 'shortcut_copy';
  schedule: {
    interval?: string | null; cron_expression?: string | null; enabled?: boolean; timezone?: string;
    overlap_policy?: 'skip' | 'buffer_one' | 'cancel_other'; start_at?: string | null; end_at?: string | null;
    remaining_actions?: number | null;
  };
  workflow_access?: WorkflowConsentRequest | null;
}
export interface ProgramScheduleView {
  definition: { schedule_id: string; owner: ProgramDefinition['owner']; request: CreateProgramSchedule; version: number };
  status: 'active' | 'paused' | 'completed'; total_runs: number; recent_runs: string[]; next_actions: string[];
  remaining_actions: number | null; authorization_id: string | null; workflow_access_consent: WorkflowConsent | null;
}
export async function createProgramSchedule(request: CreateProgramSchedule, requestKey?: string, teamId?: string, signal?: AbortSignal): Promise<ProgramScheduleView> {
  return (await api.post<ProgramScheduleView>('/program-schedules', request, {
    headers: requestKey ? { 'Idempotency-Key': requestKey } : undefined, params: { teamId }, signal,
  })).data;
}
export async function getProgramSchedule(id: string, teamId?: string, signal?: AbortSignal): Promise<ProgramScheduleView> {
  return (await api.get<ProgramScheduleView>(`/program-schedules/${encodeURIComponent(id)}`, { params: { teamId }, signal })).data;
}
export async function listProgramSchedules(teamId?: string, signal?: AbortSignal): Promise<ProgramScheduleView[]> {
  return (await api.get<ProgramScheduleView[]>('/program-schedules', { params: { teamId }, signal })).data;
}
export async function revokeProgramScheduleAccess(id: string, teamId?: string, signal?: AbortSignal): Promise<void> {
  await api.delete(`/program-schedules/${encodeURIComponent(id)}/workflow-access`, { params: { teamId }, signal });
}
export async function deleteProgramSchedule(id: string, teamId?: string, signal?: AbortSignal): Promise<void> {
  await api.delete(`/program-schedules/${encodeURIComponent(id)}`, { params: { teamId }, signal });
}
