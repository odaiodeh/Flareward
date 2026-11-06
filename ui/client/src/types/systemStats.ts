/**
 * System Statistics type definitions
 * 
 * Type definitions for system-wide statistics data structures.
 * All data is scoped to the requested time range by the backend.
 */

export type TimeRange = 'today' | '7days' | '30days' | 'all';

export interface TotalStats {
  total_runs: number;
  unique_users: number;
  programs_used: number;
}

export interface StatusBreakdown {
  [status: string]: number;
}

export interface UserActivity {
  identity_id: string;
  identity_type: string;
  display_name: string;
  run_count: number;
  programs_used: number;
  status_breakdown: StatusBreakdown;
}

export interface ProgramUsage {
  program_id: string;
  program_name: string;
  run_count: number;
  unique_users: number;
  avg_duration_seconds?: number;
  last_run_at?: string;
  completion_rate: number | null;
  program_revision: number;
  completed_runs: number;
  failed_runs: number;
  active_runs: number;
}

export interface TimeSeriesData {
  period: string;
  count: number;
}

export interface SystemStatsResponse {
  total_stats: TotalStats;
  status_breakdown: StatusBreakdown;
  owner_activity: UserActivity[];
  top_owners: UserActivity[];
  owner_offset: number;
  owner_limit: number;
  time_series_truncated: boolean;
  top_programs: ProgramUsage[];
  time_series?: TimeSeriesData[];
  generated_at: string;
}

