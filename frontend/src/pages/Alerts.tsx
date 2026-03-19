import { useState } from 'react';
import { CheckCircle, Filter } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import PageContainer from '../components/ui/PageContainer';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import { useIncidents, useResolveIncident } from '../hooks/useIncidents';
import type { Incident } from '../api/alerts';

type Tab = 'active' | 'resolved';
type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';
const tabs: Tab[] = ['active', 'resolved'];
const severities: SeverityFilter[] = ['all', 'critical', 'high', 'medium', 'low'];

function severityLevel(severity: number | null): 'critical' | 'high' | 'medium' | 'low' {
  if (!severity) return 'low';
  if (severity >= 5) return 'critical';
  if (severity >= 4) return 'high';
  if (severity >= 3) return 'medium';
  return 'low';
}

export default function Alerts() {
  const [tab, setTab] = useState<Tab>('active');
  const [severity, setSeverity] = useState<SeverityFilter>('all');

  const { data: activeIncidents = [], isLoading: activeLoading } = useIncidents('active');
  const { data: resolvedIncidents = [], isLoading: resolvedLoading } = useIncidents('resolved');
  const resolve = useResolveIncident();

  const isLoading = activeLoading || resolvedLoading;

  const all = tab === 'active' ? activeIncidents : resolvedIncidents;
  const filtered = severity === 'all'
    ? all
    : all.filter((i) => severityLevel(i.severity) === severity);

  const tabCounts = { active: activeIncidents.length, resolved: resolvedIncidents.length };

  if (isLoading) return <PageContainer><Spinner className="h-64" /></PageContainer>;

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
        {filtered.length === 0 && (
          <div className="text-center py-16 text-[#5E6A7A] text-[13px]">No incidents in this category.</div>
        )}
        {filtered.map((incident: Incident) => (
          <div key={incident.id} className="bg-[#1A2230] border border-[#1E2A3A] rounded-xl p-4 flex items-start gap-4 transition-all duration-150 ease-in-out hover:border-[#2A3A4E]">
            <Badge level={severityLevel(incident.severity)} />
            <div className="flex-1 min-w-0">
              <h3 className="text-[15px] font-medium text-[#F4F5F7]">{incident.incident_type}</h3>
              {incident.description && (
                <p className="text-[13px] text-[#9BA3B0] mt-1">{incident.description}</p>
              )}
              <div className="flex items-center gap-3 mt-2">
                {incident.segment_id && (
                  <span className="text-[11px] text-[#5E6A7A]">Segment: {incident.segment_id}</span>
                )}
                <span className="text-[11px] text-[#5E6A7A]">
                  {formatDistanceToNow(new Date(incident.started_at), { addSuffix: true })}
                </span>
                {incident.source && (
                  <span className="text-[11px] text-[#5E6A7A]">via {incident.source}</span>
                )}
              </div>
            </div>
            {tab === 'active' && (
              <Button
                variant="secondary" size="sm"
                onClick={() => resolve.mutate(incident.id)}
              >
                <CheckCircle size={12} />Resolve
              </Button>
            )}
          </div>
        ))}
      </div>
    </PageContainer>
  );
}
