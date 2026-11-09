import api from '@/http/axiosAgentConfig';

export interface UserApprovalStatus {
  approved: boolean;
  username: string;
}

export interface ApproveUserResponse {
  status: string;
  message: string;
  username: string;
  approved: boolean;
}

/**
 * Check if the authenticated user has approved the AI transparency notice.
 * Username is resolved server-side from the session cookie.
 */
export async function checkUserApproval(): Promise<UserApprovalStatus> {
  const response = await api.get<UserApprovalStatus>(
    '/consents/ai-transparency',
  );
  return response.data;
}

/**
 * Record the authenticated user's approval of the AI transparency notice.
 * Username is resolved server-side from the session cookie.
 */
export async function approveUser(): Promise<ApproveUserResponse> {
  const response = await api.post<ApproveUserResponse>(
    '/consents/ai-transparency',
  );
  return response.data;
}

