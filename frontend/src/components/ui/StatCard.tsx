import type { LucideIcon } from 'lucide-react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import clsx from 'clsx';
import Card from './Card';
import MiniChart from './MiniChart';

interface StatCardProps {
  icon: LucideIcon; label: string; value: string | number;
  trend?: number; trendDirection?: 'up' | 'down';
  sparkline?: { v: number }[]; className?: string;
}

export default function StatCard({ icon: Icon, label, value, trend, trendDirection = 'up', sparkline, className }: StatCardProps) {
  const isPositive = trendDirection === 'up';
  return (
    <Card className={clsx('flex flex-col gap-3', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center">
            <Icon size={18} className="text-[#D4915E]" />
          </div>
          <span className="text-[13px] font-medium text-[#9BA3B0] tracking-[0.01em]">{label}</span>
        </div>
        {trend !== undefined && (
          <div className={clsx('flex items-center gap-1 text-[11px] font-medium', isPositive ? 'text-[#4EA86A]' : 'text-[#E85D5D]')}>
            {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className="text-[28px] font-bold tracking-[-0.02em] text-[#F4F5F7]">{value}</div>
      {sparkline && <div className="mt-1"><MiniChart data={sparkline} /></div>}
    </Card>
  );
}
