import api from '@/http/axiosAgentConfig';
import type { JsonValue } from '@shared/json';
import type { ResourceKey, ResourceSourceRef } from '@/types/workspace';
import type { ExecutionProfileCatalog } from '@/api/catalog';

export interface ProgramRef { program_id: string; revision: number }
export type ProgramTarget = ProgramRef | ProgramBody;
export interface ProgramDescriptor {
  key: string; version: string; name: string; description: string;
  configuration_schema: Record<string, JsonValue>;
  input_schema: Record<string, JsonValue> | null;
  output_schema: Record<string, JsonValue> | null;
}
export interface ApplicationDefinition {
  kind: 'application'; implementation: string; version: string;
  config: Record<string, JsonValue>; children: Record<string, ProgramTarget>;
  environments: Record<string, string>;
  child_environment_imports: Record<string, Record<string, string>>;
}
export type ProgramBinding = { kind: 'path'; path: (string | number)[] } | { kind: 'literal'; value: JsonValue };
export type ProgramBindings = Record<string, ProgramBinding>;
export type ProgramProjection = ProgramBindings | ProgramBinding;
export interface ExecutionSelection { profile?: string | null; environment?: string | null }
interface GraphStepBase { uid: string; max_attempts: number; metadata: Record<string, JsonValue> }
export interface ProgramCallStep extends GraphStepBase {
  kind: 'program'; program: ProgramTarget; inputs: ProgramProjection; outputs: ProgramBindings;
  environment_imports: Record<string, string>;
}
export interface ResourceStep extends GraphStepBase {
  kind: 'element' | 'operation'; element: ResourceKey;
  execution: ExecutionSelection; inputs?: ProgramProjection; outputs?: ProgramBindings; description?: string;
}
export type GraphStep = ProgramCallStep | ResourceStep;
export interface ResourceDefinition {
  key: ResourceKey; type_key: string; name: string; config: Record<string, JsonValue>; implementation_version: string;
}
export interface ResourceSelection { source: ResourceSourceRef; adoption: 'reject' | 'replace'; body_path?: string[] }
export interface GraphDefinition {
  kind: 'graph'; steps: GraphStep[]; resources: ResourceDefinition[];
  edges: Record<string, string[]>;
  conditions: { source: string; condition: { category: string; rid: string }; branches: Record<string, string>; execution: ExecutionSelection }[];
  entry: string; exit: string; inputs: ProgramBindings; outputs: ProgramProjection;
  environments: Record<string, string>; recursion_limit: number;
  join_policy?: 'active' | 'all';
  write_policy?: 'ordered' | 'reduce';
}
export interface ProgramBody {
  implementation: ApplicationDefinition | GraphDefinition;
  input_schema: Record<string, JsonValue>; output_schema: Record<string, JsonValue>;
  execution_profile: string | null;
}
export interface ProgramDefinition extends ProgramBody {
  program_id: string; name: string;
  owner: { type: 'user' | 'team'; id: string; display_name: string };
}
export interface ProgramRevision { definition: ProgramDefinition; revision: number; content_digest: string }
export interface ProgramPresentation { positions: Record<string, { x: number; y: number }> }
export interface ProgramDraft { definition: ProgramDefinition; version: number; presentation: ProgramPresentation }
export interface ProgramValidation {
  version: number; valid: boolean;
  issues: { code: 'INVALID_TOPOLOGY' | 'INVALID_CONFIGURATION' | 'INVALID_CONSTRUCTION' | 'INVALID_PROGRAM_REFERENCE' | 'INVALID_BINDING'; message: string; path: (string | number)[]; severity: 'error' }[];
}
export interface SaveProgramDraft {
  definition: ProgramDefinition; expected_version: number; presentation?: ProgramPresentation;
  resource_selections?: ResourceSelection[];
}
export interface ProgramSummary {
  program_id: string; name: string; kind: ProgramDefinition['implementation']['kind']; draft_version: number;
}
export interface ProgramPage { programs: ProgramSummary[]; next_cursor: string | null }
export interface RevisionSummary { program: ProgramRef; content_digest: string }
export interface RevisionPage { revisions: RevisionSummary[]; next_cursor: number | null }
export interface WorkLimits { max_dispatches: number; max_children: number; max_depth: number }
export interface WorkflowAccess {
  purpose: string; scope: Record<string, JsonValue>;
  ttl_seconds?: number; renewable_for_seconds?: number | null;
}
export interface WorkflowAccessApproval {
  owner: ProgramDefinition['owner']; approved_by: { type: 'user'; id: string; display_name: string };
  root_execution_id: string; approved_at: string; request_sha256: string;
  requirements: WorkflowAccess[];
  consent_id: string | null;
}
export interface ProgramExecution {
  execution_id: string; phase: 'submitting' | 'running' | 'completed' | 'failed' | 'cancelled' | 'unknown';
  submission: string; inputs: JsonValue; result: JsonValue; failure: null | { message: string; kind: string };
  parent_execution_id: string | null; program: ProgramRef;
  body_path: string[]; content_digest: string;
  work_limits: WorkLimits | null;
  admitted_profiles: ExecutionProfileCatalog | null;
  workflow_access_approval: WorkflowAccessApproval | null;
  context: { root_execution_id: string };
  session_id: string | null;
  cancel_requested: boolean;
}
export interface StartProgram {
  execution_id: string; program: ProgramRef; inputs: JsonValue;
  workflow_access?: WorkflowAccess[];
}
export interface StartProgramSessionTurn {
  execution_id: string; inputs: Record<string, JsonValue>; scope?: string;
  workflow_access?: WorkflowAccess[];
}
export interface ProgramSessionExecution {
  run_id: string; active_execution_id: string | null;
  status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'LOCKED' | 'IN_USE';
  workflow_access_approval: WorkflowAccessApproval | null;
}

export async function programImplementations(signal?: AbortSignal): Promise<ProgramDescriptor[]> {
  return (await api.get<ProgramDescriptor[]>('/catalog/programs', { signal })).data;
}
export async function getProgramRevision(ref: ProgramRef, teamId?: string, signal?: AbortSignal): Promise<ProgramRevision> {
  return (await api.get<ProgramRevision>(`/programs/${encodeURIComponent(ref.program_id)}/revisions/${ref.revision}`, { params: { teamId }, signal })).data;
}
export async function listPrograms(after?: string, teamId?: string, signal?: AbortSignal): Promise<ProgramPage> {
  return (await api.get<ProgramPage>('/programs', { params: { after, teamId }, signal })).data;
}
export async function getProgramDraft(id: string, teamId?: string, signal?: AbortSignal): Promise<ProgramDraft> {
  return (await api.get<ProgramDraft>(`/programs/${encodeURIComponent(id)}`, { params: { teamId }, signal })).data;
}
export async function listProgramRevisions(id: string, before?: number, teamId?: string, signal?: AbortSignal): Promise<RevisionPage> {
  return (await api.get<RevisionPage>(`/programs/${encodeURIComponent(id)}/revisions`, { params: { before, teamId }, signal })).data;
}
export async function saveProgram(command: SaveProgramDraft, teamId?: string, signal?: AbortSignal): Promise<ProgramDraft> {
  return (await api.put<ProgramDraft>(`/programs/${encodeURIComponent(command.definition.program_id)}`, command, { params: { teamId }, signal })).data;
}
export async function publishProgram(id: string, expectedVersion: number, teamId?: string, signal?: AbortSignal): Promise<ProgramRevision> {
  return (await api.post<ProgramRevision>(`/programs/${encodeURIComponent(id)}/revisions`, { expected_version: expectedVersion }, { params: { teamId }, signal })).data;
}
export async function validateProgramDraft(id: string, expectedVersion: number, teamId?: string, signal?: AbortSignal): Promise<ProgramValidation> {
  return (await api.post<ProgramValidation>(`/programs/${encodeURIComponent(id)}/validation`, { expected_version: expectedVersion }, { params: { teamId }, signal })).data;
}
export async function startProgram(intent: StartProgram, teamId?: string, signal?: AbortSignal): Promise<ProgramExecution> {
  return (await api.post<ProgramExecution>('/executions', intent, { params: { teamId }, signal })).data;
}
export async function startProgramSessionTurn(sessionId: string, intent: StartProgramSessionTurn, teamId?: string, signal?: AbortSignal): Promise<ProgramSessionExecution> {
  return (await api.post<ProgramSessionExecution>(`/sessions/${encodeURIComponent(sessionId)}/executions`, intent, { params: { teamId }, signal })).data;
}
export async function inspectProgramExecution(id: string, teamId?: string, signal?: AbortSignal): Promise<ProgramExecution> {
  return (await api.get<ProgramExecution>(`/executions/${encodeURIComponent(id)}`, { params: { teamId }, signal })).data;
}
export async function listProgramExecutionChildren(id: string, teamId?: string, signal?: AbortSignal): Promise<ProgramExecution[]> {
  return (await api.get<ProgramExecution[]>(`/executions/${encodeURIComponent(id)}/children`, { params: { teamId }, signal })).data;
}
export async function cancelProgramExecution(id: string, teamId?: string, signal?: AbortSignal): Promise<void> {
  await api.post(`/executions/${encodeURIComponent(id)}/cancel`, undefined, { params: { teamId }, signal });
}

/** Convert an existing workflow template into an ordinary editable Program draft. */
export async function importProgramTemplate(programId: string, blueprintId: string, teamId?: string, signal?: AbortSignal): Promise<ProgramDraft> {
  return (await api.put<ProgramDraft>(`/programs/${encodeURIComponent(programId)}/blueprint`, { blueprint_id: blueprintId }, { params: { teamId }, signal })).data;
}
