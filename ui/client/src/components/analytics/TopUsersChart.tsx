import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { FaUsers } from "react-icons/fa";
import { AnalyticCard } from "./AnalyticCard";
import { CHART_TOOLTIP_CONTENT_STYLE, CHART_TOOLTIP_LABEL_STYLE } from "./analyticsHelpers";

interface TopUsersChartProps {
  topUsersData: Array<{
    name: string;
    fullName: string;
    runs: number;
    programs: number;
    completed: number;
    failed: number;
  }>;
  colors: Record<string, string>;
}

export function TopUsersChart({ topUsersData, colors }: TopUsersChartProps) {
  return (
    <AnalyticCard
      title="Top Owners by Recorded Executions"
      icon={<FaUsers style={{ color: colors.info }} />}
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={topUsersData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="name" 
            stroke="#9CA3AF" 
            angle={-45} 
            textAnchor="end" 
            height={80}
            style={{ fontSize: '12px' }}
          />
          <YAxis stroke="#9CA3AF" style={{ fontSize: '12px' }} />
          <Tooltip 
            contentStyle={CHART_TOOLTIP_CONTENT_STYLE}
            labelStyle={CHART_TOOLTIP_LABEL_STYLE}
            formatter={(value, name) => [value, name === 'runs' ? 'Total Runs' : 'Programs']}
          />
          <Bar dataKey="runs" fill={colors.primary} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </AnalyticCard>
  );
}
