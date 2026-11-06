import axios from '@/http/axiosAgentConfig';
import type { SystemStatsResponse, TimeRange, UserActivity } from '@/types/systemStats';

interface RunCounts { run_count: number; status_breakdown: Record<string, number> }
interface OwnerActivity extends RunCounts { identity_id: string; identity_type: string; programs_used: number }
interface ProgramUsage extends RunCounts {
  program: { program_id: string; revision: number }; program_name: string | null;
  unique_owners: number; avg_duration_seconds: number | null; last_run_at: string | null;
  completion_rate: number | null;
}
interface SystemReport {
  root_executions: number; unique_owners: number; programs_used: number;
  status_breakdown: Record<string, number>; owner_activity: OwnerActivity[]; top_owners: OwnerActivity[];
  owner_offset: number; owner_limit: number; top_programs: ProgramUsage[];
  time_series: { period: string; count: number }[]; time_series_truncated: boolean; generated_at: string;
}
const statuses = (counts: Record<string, number>) => Object.fromEntries(
  Object.entries(counts).map(([phase, count]) => [phase.toUpperCase(), count]),
);
const ownerView = (row: OwnerActivity): UserActivity => ({
  ...row, display_name: '', status_breakdown: statuses(row.status_breakdown),
});

export async function fetchSystemWideStats(timeRange: TimeRange = 'all', ownerOffset = 0, ownerLimit = 100): Promise<SystemStatsResponse> {
  const { data } = await axios.get<SystemReport>('/reporting/system', {
    params: { time_range: timeRange, owner_offset: ownerOffset, owner_limit: ownerLimit },
  });
  return {
    total_stats: { total_runs: data.root_executions, unique_users: data.unique_owners, programs_used: data.programs_used },
    status_breakdown: statuses(data.status_breakdown),
    owner_activity: data.owner_activity.map(ownerView), top_owners: data.top_owners.map(ownerView),
    owner_offset: data.owner_offset, owner_limit: data.owner_limit,
    top_programs: data.top_programs.map(row => ({
      program_id: row.program.program_id, program_revision: row.program.revision,
      program_name: row.program_name ?? row.program.program_id,
      run_count: row.run_count, unique_users: row.unique_owners,
      completion_rate: row.completion_rate, avg_duration_seconds: row.avg_duration_seconds ?? undefined,
      last_run_at: row.last_run_at ?? undefined, completed_runs: row.status_breakdown.completed ?? 0,
      failed_runs: row.status_breakdown.failed ?? 0, active_runs: row.status_breakdown.running ?? 0,
    })),
    time_series: data.time_series, time_series_truncated: data.time_series_truncated, generated_at: data.generated_at,
  };
}
