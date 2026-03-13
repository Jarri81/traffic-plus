import { Route as RouteIcon, ShieldAlert, Bell, Camera } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import PageContainer from '../components/ui/PageContainer';
import StatCard from '../components/ui/StatCard';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import RiskGauge from '../components/ui/RiskGauge';
import Table from '../components/ui/Table';
import { stats, trafficFlow, systemRiskScore, segments, alerts, sparklineData } from '../data/mock';
import type { Segment, Alert } from '../data/mock';
import { chartColors } from '../design/tokens';

const topRiskSegments = [...segments].sort((a, b) => b.riskScore - a.riskScore).slice(0, 5);
const recentAlerts = alerts.filter((a) => a.status === 'active').slice(0, 5);

const segmentColumns = [
  { key: 'name', header: 'Segment', render: (r: Segment) => <span className="text-[#F4F5F7] font-medium">{r.name}</span> },
  { key: 'location', header: 'Location', render: (r: Segment) => <span className="text-[#9BA3B0]">{r.location}</span> },
  { key: 'risk', header: 'Risk', render: (r: Segment) => <Badge level={r.riskLevel} /> },
  { key: 'score', header: 'Score', render: (r: Segment) => <span className="text-[#F4F5F7] font-semibold">{r.riskScore}</span> },
];

export default function Dashboard() {
  return (
    <PageContainer className="flex flex-col gap-6">
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={RouteIcon} label="Active Segments" value={stats.activeSegments} trend={8} trendDirection="up" sparkline={sparklineData(12)} />
        <StatCard icon={ShieldAlert} label="Average Risk Score" value={stats.averageRisk} trend={3} trendDirection="down" sparkline={sparklineData(53)} />
        <StatCard icon={Bell} label="Open Alerts" value={stats.openAlerts} trend={12} trendDirection="up" sparkline={sparklineData(7)} />
        <StatCard icon={Camera} label="Cameras Online" value={`${stats.camerasOnline}/${stats.totalCameras}`} trend={2} trendDirection="up" sparkline={sparklineData(13)} />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2">
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Traffic Flow — Last 24h</h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trafficFlow}>
              <defs>
                <linearGradient id="flowGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColors.primary} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={chartColors.primary} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColors.secondary} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={chartColors.secondary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
              <XAxis dataKey="time" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} labelStyle={{ color: '#9BA3B0' }} />
              <Area type="monotone" dataKey="predicted" stroke={chartColors.secondary} fill="url(#predGrad)" strokeWidth={1.5} dot={false} name="Predicted" />
              <Area type="monotone" dataKey="flow" stroke={chartColors.primary} fill="url(#flowGrad)" strokeWidth={2} dot={false} name="Actual" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <Card className="flex flex-col items-center justify-center">
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">System Risk Score</h2>
          <RiskGauge score={systemRiskScore} size={220} />
        </Card>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Top Risk Segments</h2>
          <Table columns={segmentColumns} data={topRiskSegments} keyExtractor={(r) => r.id} />
        </Card>
        <Card>
          <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Recent Alerts</h2>
          <div className="flex flex-col gap-3">
            {recentAlerts.map((alert: Alert) => (
              <div key={alert.id} className="flex items-start gap-3 p-3 rounded-lg bg-[#111820] border border-[#1E2A3A]">
                <Badge level={alert.severity} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-[#F4F5F7]">{alert.segmentName}</p>
                  <p className="text-[11px] text-[#9BA3B0] mt-0.5 truncate">{alert.description}</p>
                </div>
                <span className="text-[11px] text-[#5E6A7A] whitespace-nowrap">
                  {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </PageContainer>
  );
}