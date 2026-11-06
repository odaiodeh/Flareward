import api from '@/http/axiosAgentConfig';
import type { JsonValue } from '@shared/json';

export type ReviewDecision = 'approve' | 'reject';
export type ReviewStatus = 'pending' | 'decided' | 'expired' | 'cancelled' | 'superseded';
export interface ReviewRecord {
  review_id: string;
  owner: { type: 'user' | 'team'; id: string; display_name: string };
  root_execution_id: string;
  execution_id: string;
  key: string;
  policy: string;
  reviewers: string[];
  specification: {
    prompt: string;
    subject: JsonValue;
    response_schema: Record<string, JsonValue>;
    decisions: ReviewDecision[];
    timeout_seconds: number;
  };
  created_at: string;
  expires_at: string;
  status: ReviewStatus;
  response: null | {
    key: string;
    decision: ReviewDecision;
    data: JsonValue;
    issued_by: { type: 'user'; id: string };
    recorded_at: string;
  };
  superseded_by: string | null;
  delivery_pending: boolean;
  revision: number;
}
export interface ReviewPage { reviews: ReviewRecord[]; next_cursor: string | null }
export interface ReviewSubmission {
  key: string;
  expected_revision: number;
  decision: ReviewDecision;
  data: JsonValue;
}

/** Assigned-human inbox; workflow bearer capabilities never enter this client. */
export async function listReviews(signal?: AbortSignal, after = ''): Promise<ReviewPage> {
  return (await api.get<ReviewPage>('/reviews/inbox', { params: { after }, signal })).data;
}

export async function getReview(id: string, signal?: AbortSignal): Promise<ReviewRecord> {
  return (await api.get<ReviewRecord>(`/reviews/${encodeURIComponent(id)}`, { signal })).data;
}

/** Owner inspection never grants the assigned reviewer's decision authority. */
export async function executionReviews(root: string, teamId?: string, after = '', signal?: AbortSignal): Promise<ReviewPage> {
  return (await api.get<ReviewPage>(`/executions/${encodeURIComponent(root)}/reviews`, { params: { teamId, after }, signal })).data;
}

export async function respondToReview(id: string, submission: ReviewSubmission, signal?: AbortSignal): Promise<ReviewRecord> {
  return (await api.post<ReviewRecord>(`/reviews/${encodeURIComponent(id)}/responses`, submission, { signal })).data;
}
