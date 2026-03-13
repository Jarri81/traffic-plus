import { useState } from 'react';
import { CheckCircle, Eye, Filter } from 'lucide-react';
import clsx from 'clsx';
import PageContainer from '../components/ui/PageContainer';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { alerts } from '../data/mock';
import type { Alert } from '../data/mock';

type Tab = 'active' | 'acknowledged' | 'resolved';
type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

export default function Alerts() {
  const [tab, setTab] = useState<Tab>('active');
  const [severity, setSeverity] = useState<SeverityFilter>('all');
  const tabs: Tab[] = ['active', 'acknowledged', 'resolved'];
  const severities: SeverityFilter[] = ['all', 'critical', 'high', 'medium', 'low'];
  const filtered = alerts.filter((a) => a.status === tab).filter((a) => severity === 'all' || a.severity === severity);
  const tabCounts = {
    active: alerts.filter((a) => a.status === 'active').length,
    acknowledged: alerts.filter((a) => a.status === 'acknowledged').length,
    resolved: alerts.filter((a) => a.status === 'resolved').length,
  };
  return (
    <PageContainer className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-[#1A2230] rounded-lg p-1 border border-[#1E2A3A]">
          {tabs.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx('px-4 py-2 rounded-md text-[13px] font-medium capitalize transition-all duration-150 ease-in-out',
                tab === t ? 'bg-[#232E3F] text-[#F4F5F7]' : 'text-[#5E6A7A] hover:text-[#9BA3B0]')}>
              {t}<span className="ml-1.5 text-[11px] text-[#5E6A7A]">({tabCounts[t]})</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-[#5E6A7A]" />
          {severities.map((s) => (
            <button key={s} onClick={() => setSeverity(s)}
              className={clsx('px-2.5 py-1 rounded-md text-[11px] font-medium capitalize transition-all duration-150 ease-in-out',
                severity === s ? 'bg-[#D4915E]/15 text-[#D4915E]' : 'text-[#5E6A7A] hover:text-[#9BA3B0]')}>
              {s}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-3">
        {filtered.length === 0 && <div className="text-center py-16 text-[#5E6A7A] text-[13px]">No alerts in this category.</div>}
        {filtered.map((alert: Alert) => (
          <div key={alert.id} className="bg-[#1A2230] border border-[#1E2A3A] rounded-xl p-4 flex items-start gap-4 transition-all duration-150 ease-in-out hover:border-[#2A3A4E]">
            <Badge level={alert.severity} />
            <div className="flex-1 min-w-0">
              <h3 className="text-[15px] font-medium text-[#F4F5F7]">{alert.segmentName}</h3>
              <p className="text-[13px] text-[#9BA3B0] mt-1">{alert.description}</p>
              <p className="text-[11px] text-[#5E6A7A] mt-2">{new Date(alert.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {tab === 'active' && (
                <>
                  <Button variant="secondary" size="sm"><Eye size={12} />Acknowledge</Button>
                  <Button variant="secondary" size="sm"><CheckCircle size={12} />Resolve</Button>
                </>
              )}
              {tab === 'acknowledged' && <Button variant="secondary" size="sm"><CheckCircle size={12} />Resolve</Button>}
            </div>
          </div>
        ))}
      </div>
    </PageContainer>
  );
}