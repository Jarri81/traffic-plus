import { useState } from 'react';
import { Plus, MapPin, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import { useSegments, useRiskSummary } from '../hooks/useSegments';

type FilterLevel = 'all' | 'critical' | 'high' | 'medium' | 'low';
const filters: FilterLevel[] = ['all', 'critical', 'high', 'medium', 'low'];

export default function Segments() {
  const [filter, setFilter] = useState<FilterLevel>('all');
  const { data: segments, isLoading: segLoading } = useSegments();
  const { data: riskSummary, isLoading: riskLoading } = useRiskSummary();

  const riskMap = Object.fromEntries((riskSummary ?? []).map((r) => [r.segment_id, r]));

  const enriched = (segments ?? []).map((s) => ({
    ...s,
    riskScore: riskMap[s.id]?.score ?? 0,
    riskLevel: (riskMap[s.id]?.level ?? 'low') as FilterLevel,
  }));

  const filtered = filter === 'all' ? enriched : enriched.filter((s) => s.riskLevel === filter);

  if (segLoading || riskLoading) return <PageContainer><Spinner className="h-64" /></PageContainer>;

  return (
    <PageContainer className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">{filtered.length} Segments</h2>
          <div className="flex items-center gap-1 ml-4">
            {filters.map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={clsx('px-3 py-1.5 rounded-lg text-[11px] font-medium tracking-[0.01em] capitalize transition-all duration-150 ease-in-out',
                  filter === f ? 'bg-[#D4915E]/15 text-[#D4915E]' : 'text-[#5E6A7A] hover:text-[#9BA3B0] hover:bg-[#1A2230]')}>
                {f}
              </button>
            ))}
          </div>
        </div>
        <Button><Plus size={16} />Add Segment</Button>
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-20 text-[#5E6A7A] text-[13px]">
          {segments?.length === 0
            ? 'No segments in the database yet.'
            : `No ${filter} risk segments.`}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {filtered.map((seg) => (
          <Card key={seg.id} hover>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-[15px] font-semibold text-[#F4F5F7] tracking-[-0.02em]">{seg.name ?? seg.id}</h3>
                <div className="flex items-center gap-1 mt-1">
                  <MapPin size={12} className="text-[#5E6A7A]" />
                  <span className="text-[11px] text-[#5E6A7A]">{seg.pilot}</span>
                </div>
              </div>
              <Badge level={seg.riskLevel === 'all' ? 'low' : seg.riskLevel} />
            </div>
            <div className="flex items-center gap-3 text-[11px] text-[#5E6A7A] mt-2">
              {seg.speed_limit_kmh && <span>{seg.speed_limit_kmh} km/h limit</span>}
              {seg.lanes && <span>{seg.lanes} lanes</span>}
              {seg.length_m && <span>{(seg.length_m / 1000).toFixed(1)} km</span>}
            </div>
            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[#1E2A3A]">
              <div className="flex items-center gap-1.5">
                <Clock size={12} className="text-[#5E6A7A]" />
                <span className="text-[11px] text-[#9BA3B0]">
                  {formatDistanceToNow(new Date(seg.updated_at), { addSuffix: true })}
                </span>
              </div>
              <div className="ml-auto">
                <span className="text-[18px] font-bold tracking-[-0.02em] text-[#F4F5F7]">{seg.riskScore}</span>
                <span className="text-[11px] text-[#5E6A7A] ml-1">risk</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </PageContainer>
  );
}
