import { ResponsiveContainer, LineChart, Line } from 'recharts';

interface MiniChartProps { data: { v: number }[]; color?: string; height?: number; }

export default function MiniChart({ data, color = '#D4915E', height = 32 }: MiniChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}