import { FaRocket } from "react-icons/fa";
import { useMemo } from "react";
import { generateColorPalette } from "@/lib/colorUtils";
import { AnalyticCard } from "./AnalyticCard";
import type { ProgramUsage } from "@/types/systemStats";

interface TopProgramsQuickViewProps {
  programs: ProgramUsage[];
  colors: Record<string, string>;
}

export function TopProgramsQuickView({ programs, colors }: TopProgramsQuickViewProps) {
  const colorPalette = useMemo(() => {
    return generateColorPalette(colors.primary, programs?.length || 0);
  }, [colors.primary, programs?.length]);

  if (!programs || programs.length === 0) {
    return (
      <AnalyticCard
        title="Top Program Revisions"
        icon={<FaRocket style={{ color: colors.primary }} />}
      >
        <div className="flex flex-col items-center justify-center h-48 text-gray-400">
          <FaRocket className="text-4xl mb-3 opacity-30" />
          <p className="text-sm">No program data available</p>
        </div>
      </AnalyticCard>
    );
  }

  const maxRuns = Math.max(...programs.map((bp) => bp.run_count), 1);

  return (
    <AnalyticCard
      title="Top Program Revisions"
      icon={<FaRocket style={{ color: colors.primary }} />}
    >
          <div className="space-y-4">
            {programs.slice(0, 5).map((bp, idx) => {
              const percentage = (bp.run_count / maxRuns) * 100;
              const color = colorPalette[idx % colorPalette.length];
              return (
                <div key={idx} className="space-y-2">
                  <div className="flex justify-between items-center text-sm">
                    <span className="font-medium truncate max-w-[200px]" title={bp.program_name}>
                      {bp.program_name} · revision {bp.program_revision}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400 text-xs">{bp.unique_users} owners</span>
                      <span className="font-semibold" style={{ color }}>
                        {bp.run_count}
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-background-dark rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${percentage}%`,
                        backgroundColor: color
                      }}
                    />
                  </div>
                </div>
              );
            })}
            {programs.length > 5 && (
              <div className="pt-2 border-t border-gray-700 text-center">
                <p className="text-xs text-gray-500">
                  More recorded revisions in Programs
                </p>
              </div>
            )}
          </div>
    </AnalyticCard>
  );
}

