import clsx from 'clsx';

type RiskLevel = 'critical' | 'high' | 'medium' | 'low';
interface BadgeProps { level: RiskLevel; className?: string; }

const config: Record<RiskLevel, { dot: string; bg: string; text: string; label: string }> = {
  critical: { dot: 'bg-[#E85D5D]', bg: 'bg-[#E85D5D]/10', text: 'text-[#E85D5D]', label: 'Critical' },
  high: { dot: 'bg-[#E8A44C]', bg: 'bg-[#E8A44C]/10', text: 'text-[#E8A44C]', label: 'High' },
  medium: { dot: 'bg-[#D4C24E]', bg: 'bg-[#D4C24E]/10', text: 'text-[#D4C24E]', label: 'Medium' },
  low: { dot: 'bg-[#4EA86A]', bg: 'bg-[#4EA86A]/10', text: 'text-[#4EA86A]', label: 'Low' },
};

export default function Badge({ level, className }: BadgeProps) {
  const c = config[level];
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium tracking-[0.01em]', c.bg, c.text, className)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', c.dot)} />
      {c.label}
    </span>
  );
}