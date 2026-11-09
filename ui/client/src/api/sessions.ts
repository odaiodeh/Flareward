import axios from '@/http/axiosAgentConfig';
import { ChatSessionData } from '@/types/session';
import { isRecord } from '@/lib/json';

export interface CreateSessionParams {
  blueprintId: string;
  teamId?: string;
  metadata?: Record<string, any>;
  hitlEnabled?: boolean;
}

export async function createSession(params: CreateSessionParams): Promise<string> {
  const response = await axios.post<string>('/sessions/user.session.create', params);
  return response.data;
}

/**
 * Submit Session Request Parameters
 * Used for fire-and-forget background execution
 */
export interface SubmitSessionParams {
  sessionId: string;
  inputs: Record<string, any>;
  scope?: 'public' | 'private';
  teamId?: string;
  executionId?: string;
}

/**
 * Submit Session Response
 * Returned immediately with HTTP 202 - session runs in background
 */
export interface SubmitSessionResponse {
  sessionId: string;
  executionId?: string;
  workflowId?: string;
}

/**
 * Submit a session for background execution.
 * Returns immediately with HTTP 202 — the session runs asynchronously.
 * 
 * After calling this, use subscribeToSessionStream() to receive real-time events.
 * 
 * @param params - Session submission parameters
 * @returns Session ID and workflow ID (if using Temporal)
 * @throws Error if submission fails (400, 500)
 */
export async function submitSession(params: SubmitSessionParams): Promise<SubmitSessionResponse> {
  const response = await axios.post('/sessions/user.session.submit', {
    ...params, executionId: params.executionId ?? crypto.randomUUID(),
  });
  return response.data;
}

/**
 * Get the current execution status of a session.
 */
function sessionQuery(sessionId: string, teamId?: string): URLSearchParams {
  const query = new URLSearchParams({ sessionId });
  if (teamId) query.set('teamId', teamId);
  return query;
}

export async function getSessionStatus(sessionId: string, teamId?: string): Promise<string> {
  const query = sessionQuery(sessionId, teamId);
  const response = await axios.get(`/sessions/session.status.get?${query.toString()}`);
  return response.data;
}

/**
 * Cancel Session Response
 */
export interface CancelSessionResponse {
  sessionId: string;
  status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'LOCKED' | 'IN_USE';
}

/**
 * Cancel a running session.
 * Signals the backend to cancel the workflow for this session.
 * Silently ignores 409 (session already completed/failed/cancelled).
 *
 * @param sessionId - The session to cancel
 * @returns Cancel confirmation, or null if session was not cancellable
 */
export async function cancelSession(sessionId: string, teamId?: string): Promise<CancelSessionResponse | null> {
  try {
    const response = await axios.post('/sessions/session.cancel', { sessionId, teamId });
    return response.data;
  } catch (err: any) {
    if (err.response?.status === 409) {
      return null;
    }
    throw err;
  }
}

/**
 * Redis Stream Status Response
 */
export interface StreamStatusResponse {
  session_id: string;
  execution_id?: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'unknown';
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  error: string | null;
  event_count: number | null;
  last_event_id: string | null;
  is_active: boolean;
}

/**
 * Check the streaming status of a session via Redis.
 * Returns null if Redis is unavailable, session not found, or timeout.
 */
export async function getSessionStreamStatus(sessionId: string, teamId?: string): Promise<StreamStatusResponse | null> {
  try {
    const query = sessionQuery(sessionId, teamId);
    const response = await axios.get(`/sessions/session.stream.status?${query.toString()}`, {
      timeout: 5000, // 5 second timeout to prevent hanging
    });
    return response.data;
  } catch (err: any) {
    // Gracefully handle unavailable Redis, not found, or timeout
    if (err.response?.status === 503 || err.response?.status === 404 || err.code === 'ECONNABORTED') {
      return null;
    }
    console.error('Error fetching stream status:', err);
    return null;
  }
}

// ─── Session Chat (error-propagating) ─────────────────────────────────────────

export interface SessionChatData {
  messages: any[];
  status?: string;
  status_message?: string;
  blueprint_id?: string;
  blueprint_exists?: boolean;
}

/**
 * Fetch session chat data by ID.
 * Unlike the swallowing variant in use-session-management, this propagates
 * errors so callers can distinguish 403/404 from success.
 */
export async function fetchSessionChatById(sessionId: string, teamId?: string): Promise<SessionChatData> {
  const response = await axios.get('/sessions/session.chat.get', {
    params: { sessionId, teamId },
  });
  return response.data;
}

// ─── HITL Approval ────────────────────────────────────────────────────────────

export interface SubmitApprovalParams {
  sessionId: string;
  requestId: string;
  /** Native requests bind the decision to this execution; legacy servers omit it. */
  executionId?: string;
  decision: 'approve' | 'reject' | 'modify' | 'redirect';
  feedback?: string;
  modifiedArgs?: Record<string, any>;
  teamId?: string;
}

export interface SubmitApprovalResponse {
  status: 'submitted';
  sessionId: string;
  requestId: string;
  executionId?: string;
  decision: string;
}

/**
 * Submit a human decision for a pending HITL approval request.
 *
 * Resolves the pending request in the specified execution and returns the
 * backend's confirmation.
 *
 * @param params - Approval submission parameters
 */
export async function submitApproval(params: SubmitApprovalParams): Promise<SubmitApprovalResponse> {
  const response = await axios.post('/sessions/session.approval', {
    sessionId: params.sessionId,
    requestId: params.requestId,
    executionId: params.executionId,
    decision: params.decision,
    feedback: params.feedback ?? '',
    modifiedArgs: params.modifiedArgs ?? {},
    teamId: params.teamId,
  });
  return response.data;
}

// ─── HITL Auto-Approval Rules ─────────────────────────────────────────────────

export type ApprovalRuleAction = 'auto_approve' | 'auto_reject' | 'clear';

export interface SubmitApprovalRuleParams {
  executionId?: string;
  teamId?: string;
  sessionId: string;
  nodeUid?: string | null;
  toolName?: string | null;
  action: ApprovalRuleAction;
}

export interface ApprovalRules {
  approve_all: boolean;
  reject_all: boolean;
  auto_approve_tools: string[];
  auto_reject_tools: string[];
}

export interface SessionApprovalRules {
  sessionId: string;
  overrides: { global_rules: ApprovalRules; node_rules: Record<string, ApprovalRules> };
}

export interface ApprovalRuleResponse extends SessionApprovalRules {
  status: 'saved';
}

export async function getApprovalRules(sessionId: string, teamId?: string): Promise<SessionApprovalRules> {
  return (await axios.get('/sessions/session.approval.rules', { params: { sessionId, teamId } })).data;
}

/**
 * Add or clear an auto-approval rule for this session.
 *
 * Scoping is determined by which fields are present:
 *   nodeUid=null, toolName=null → global approve/reject all
 *   nodeUid=null, toolName="x"  → global rule for tool "x"
 *   nodeUid="a",  toolName=null → node "a" approve/reject all
 *   nodeUid="a",  toolName="x"  → node "a" rule for tool "x"
 */
export async function submitApprovalRule(params: SubmitApprovalRuleParams): Promise<ApprovalRuleResponse> {
  const response = await axios.post('/sessions/session.approval.rule', {
    executionId: params.executionId,
    teamId: params.teamId,
    sessionId: params.sessionId,
    nodeUid: params.nodeUid ?? null,
    toolName: params.toolName ?? null,
    action: params.action,
  });
  return response.data;
}

/**
 * Delete a session by ID.
 */
export async function deleteSession(sessionId: string, teamId?: string): Promise<void> {
  const query = sessionQuery(sessionId, teamId);
  await axios.delete(`/sessions/session.delete?${query.toString()}`);
}

/**
 * Get the full chat data for a session (output, status, status_message, etc.).
 */
export async function getSessionChat(sessionId: string, teamId?: string): Promise<{
  output: string;
  status: string;
  status_message?: string;
}> {
  const query = sessionQuery(sessionId, teamId);
  const response = await axios.get(`/sessions/session.chat.get?${query.toString()}`);
  return response.data;
}

/**
 * Get the final state of a session after execution completes.
 */
export async function getSessionState(sessionId: string, teamId?: string): Promise<{ output: string }> {
  const query = sessionQuery(sessionId, teamId);
  const response = await axios.get<unknown>(`/sessions/session.state.get?${query.toString()}`);
  if (!isRecord(response.data) || typeof response.data.output !== 'string') {
    throw new Error('Session state contains an invalid output');
  }
  return { output: response.data.output };
}

/**
 * List sessions for a user.
 * 
 * @param params - URLSearchParams containing the list of sessions
 * @returns List of sessions and pagination information
 */
export async function listSessions(params: URLSearchParams): Promise<ListSessionsResponse> {
  const response = await axios.get('/sessions/session.user.list', { params });
  return response.data;
}

export interface ListSessionsResponse {
  sessions: ChatSessionData[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

/**
 * Subscribe to a session's Redis stream.
 * Returns the streaming response; HTTP and transport failures propagate.
 * 
 * The stream replays all events from the beginning, then blocks and streams
 * live events as they arrive. Connection stays open until session completes.
 * 
 * @param sessionId - The session to subscribe to
 */
export interface StreamSubscriptionOptions {
  teamId?: string;
  executionId?: string;
  after?: string;
  signal?: AbortSignal;
}

export async function subscribeToSessionStream(
  sessionId: string, options: StreamSubscriptionOptions = {},
): Promise<Response> {
  const query = sessionQuery(sessionId, options.teamId);
  if (options.executionId) query.set('executionId', options.executionId);
  if (options.after) query.set('after', options.after);
  const response = await fetch(
    `/api/sessions/session.subscribe?${query.toString()}`,
    {
      method: 'GET',
      signal: options.signal,
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/x-ndjson',
      },
    }
  );

  if (!response.ok) {
    await response.body?.cancel().catch(() => undefined);
    throw new Error(`Stream subscription failed (HTTP ${response.status})`);
  }

  return response;
}
