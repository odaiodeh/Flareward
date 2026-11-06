import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FaRocket, FaChartBar } from "react-icons/fa";
import { useMemo } from "react";
import { generateColorPalette } from "@/lib/colorUtils";
import { AnalyticCard } from "./AnalyticCard";
import { formatDuration, getSuccessRateColor } from "./analyticsHelpers";
import { formatRelativeTimestamp } from "@/utils";
import type { ProgramUsage } from "@/types/systemStats";

interface ProgramsTableProps {
  programs: ProgramUsage[];
  colors: Record<string, string>;
}

export function ProgramsTable({ programs, colors }: ProgramsTableProps) {
  const colorPalette = useMemo(() => {
    return generateColorPalette(colors.primary, programs?.length || 0);
  }, [colors.primary, programs?.length]);

  return (
    <AnalyticCard
      title="Most Used Programs"
      icon={<FaRocket style={{ color: colors.primary }} />}
    >
      <div className="overflow-x-auto">
        <TooltipProvider>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Program revision</TableHead>
                <TableHead className="text-right">Total Runs</TableHead>
                <TableHead className="text-right">Avg Duration</TableHead>
                <TableHead className="text-right">Last Run</TableHead>
                <TableHead className="text-right">Operational completion</TableHead>
                <TableHead className="text-right">Owners</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {programs.length > 0 ? (
                programs.map((bp, idx) => {
                  const color = colorPalette[idx % colorPalette.length];
                  return (
                    <TableRow key={idx} className="hover:bg-muted/50">
                      <TableCell className="font-medium text-sm max-w-[200px] truncate" title={bp.program_name}>
                        {bp.program_name} · revision {bp.program_revision}
                      </TableCell>
                      <TableCell className="text-right text-sm font-semibold" style={{ color }}>
                        {bp.run_count}
                      </TableCell>
                      <TableCell className="text-right text-sm text-gray-400">
                        {formatDuration(bp.avg_duration_seconds)}
                      </TableCell>
                      <TableCell className="text-right text-sm text-gray-400">
                        {bp.last_run_at ? formatRelativeTimestamp(bp.last_run_at) : "—"}
                      </TableCell>
                      <TableCell className="text-right text-sm">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="inline-flex items-center gap-1.5 cursor-default">
                              <span className={bp.completion_rate === null ? "text-muted-foreground" : getSuccessRateColor(bp.completion_rate)}>
                                {bp.completion_rate === null ? "—" : `${bp.completion_rate.toFixed(1)}%`}
                              </span>
                              <FaChartBar className="w-3 h-3 text-gray-500" />
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs">
                            <div className="text-xs space-y-1">
                              <p className="font-semibold mb-1.5">Execution Breakdown</p>
                              <div className="flex justify-between gap-4">
                                <span className="text-green-400">Completed</span>
                                <span className="font-medium">{bp.completed_runs ?? 0}</span>
                              </div>
                              <div className="flex justify-between gap-4">
                                <span className="text-red-400">Failed</span>
                                <span className="font-medium">{bp.failed_runs ?? 0}</span>
                              </div>
                              {(bp.active_runs ?? 0) > 0 && (
                                <div className="flex justify-between gap-4">
                                  <span className="text-yellow-400">Observed running</span>
                                  <span className="font-medium">{bp.active_runs}</span>
                                </div>
                              )}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell className="text-right text-sm">{bp.unique_users}</TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-6 text-gray-400">
                    No program data available
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TooltipProvider>
      </div>
    </AnalyticCard>
  );
}
