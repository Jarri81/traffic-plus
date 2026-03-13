import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import { riskFactors, riskDistribution, historicalRisk } from '../data/mock';
import { chartColors } from '../design/tokens';

const featureImportance = [
  { name: 'Traffic Density', importance: 0.28, color: chartColors.primary },
  { name: 'Speed Variance', importance: 0.22, color: chartColors.high },
  { name: 'Time Patterns', importance: 0.18, color: chartColors.secondary },
  { name: 'Incident History', importance: 0.14, color: chartColors.medium },
  { name: 'Weather Impact', importance: 0.09, color: chartColors.critical },
  { name: 'Maintenance', importance: 0.05, color: chartColors.muted },
  { name: 'Road Geometry', importance: 0.04, color: chartColors.low },
];

export default function RiskAnalysis() {
  return (
    <PageContainer className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-5">Risk Factor Contributions</h2>
          <div className="flex flex-col gap-3">
            {riskFactors.map((factor) => {
              const pct = Math.round((factor.value / factor.maxValue) * 100);
              const barColor = pct >= 75 ? '#E85D5D' : pct >= 50 ? '#E8A44C' : pct >= 25 ? '#D4C24E' : '#4EA86A';
              return (
                <div key={factor.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[13px] text-[#9BA3B0]">{factor.name}</span>
                    <span className="text-[13px] font-semibold text-[#F4F5F7]">{factor.value}%</span>
                  </div>
                  <div className="h-2 bg-[#111820] rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, backgroundColor: barColor }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
        <Card className="flex flex-col items-center">
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-5 self-start">Risk Distribution</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={riskDistribution} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value" stroke="none">
                {riskDistribution.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-2">
            {riskDistribution.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                <span className="text-[11px] text-[#9BA3B0]">{d.name} ({d.value})</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card>
        <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Historical Risk Trend — 30 Days</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={historicalRisk}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="day" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} interval={4} />
            <YAxis domain={[0, 100]} tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} />
            <Line type="monotone" dataKey="score" stroke={chartColors.primary} strokeWidth={2} dot={false} name="Risk Score" />
          </LineChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Feature Importance (SHAP Analysis)</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={featureImportance} layout="vertical" margin={{ left: 100 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} horizontal={false} />
            <XAxis type="number" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 0.35]} />
            <YAxis type="category" dataKey="name" tick={{ fill: chartColors.text, fontSize: 12 }} axisLine={false} tickLine={false} width={100} />
            <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} formatter={(value) => [(Number(value) * 100).toFixed(0) + '%', 'Importance']} />
            <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
              {featureImportance.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </PageContainer>
  );
}