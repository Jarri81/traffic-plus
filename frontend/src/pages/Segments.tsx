import { useState } from 'react';
import { Plus, MapPin, Camera, Clock } from 'lucide-react';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { segments } from '../data/mock';
import type { Segment } from '../data/mock';
import clsx from 'clsx';

type FilterLevel = 'all' | 'critical' | 'high' | 'medium' | 'low';

export default function Segments() {
  const [filter, setFilter] = useState<FilterLevel>('all');
  const filtered = filter === 'all' ? segments : segments.filter((s) => s.riskLevel === filter);
  const filters: FilterLevel[] = ['all', 'critical', 'high', 'medium', 'low'];
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
      <div className="grid grid-cols-3 gap-4">
        {filtered.map((seg: Segment) => (
          <Card key={seg.id} hover>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-[15px] font-semibold text-[#F4F5F7] tracking-[-0.02em]">{seg.name}</h3>
                <div className="flex items-center gap-1 mt-1">
                  <MapPin size={12} className="text-[#5E6A7A]" />
                  <span className="text-[11px] text-[#5E6A7A]">{seg.location}</span>
                </div>
              </div>
              <Badge level={seg.riskLevel} />
            </div>
            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[#1E2A3A]">
              <div className="flex items-center gap-1.5">
                <Camera size={12} className="text-[#5E6A7A]" />
                <span className="text-[11px] text-[#9BA3B0]">{seg.cameraCount} cameras</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock size={12} className="text-[#5E6A7A]" />
                <span className="text-[11px] text-[#9BA3B0]">{seg.lastUpdated}</span>
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