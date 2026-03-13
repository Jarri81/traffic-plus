import clsx from 'clsx';

interface RiskGaugeProps { score: number; size?: number; className?: string; }

function getColor(score: number): string {
  if (score >= 75) return '#E85D5D';
  if (score >= 50) return '#E8A44C';
  if (score >= 25) return '#D4C24E';
  return '#4EA86A';
}
function getLabel(score: number): string {
  if (score >= 75) return 'Critical';
  if (score >= 50) return 'Elevated';
  if (score >= 25) return 'Moderate';
  return 'Low';
}

export default function RiskGauge({ score, size = 200, className }: RiskGaugeProps) {
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const cy = size / 2;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = getColor(score);
  const label = getLabel(score);
  return (
    <div className={clsx('flex flex-col items-center', className)}>
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        <path d={`M ${strokeWidth / 2} ${cy} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${cy}`} fill="none" stroke="#1E2A3A" strokeWidth={strokeWidth} strokeLinecap="round" />
        <path d={`M ${strokeWidth / 2} ${cy} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${cy}`} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeDasharray={`${progress} ${circumference}`} style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }} />
      </svg>
      <div className="flex flex-col items-center -mt-12">
        <span className="text-[40px] font-bold tracking-[-0.02em]" style={{ color }}>{score}</span>
        <span className="text-[13px] font-medium text-[#9BA3B0] tracking-[0.01em]">{label}</span>
      </div>
    </div>
  );
}
