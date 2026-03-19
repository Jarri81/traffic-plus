import PageContainer from '../components/ui/PageContainer';
import SegmentMap from '../components/ui/SegmentMap';
import { useRiskSummary } from '../hooks/useSegments';

const RISK_COLORS = { critical: '#E85D5D', high: '#E8A44C', medium: '#D4C24E', low: '#4EA86A' };

export default function MapView() {
  const { data: riskSummary } = useRiskSummary();

  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  (riskSummary ?? []).forEach((r) => {
    const l = r.level as keyof typeof counts;
    if (l in counts) counts[l]++;
  });

  return (
    <PageContainer className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">Network Map</h2>
          <p className="text-[13px] text-[#5E6A7A] mt-0.5">Road segments coloured by live risk score</p>
        </div>
        <div className="flex items-center gap-4">
          {Object.entries(RISK_COLORS).map(([level, color]) => (
            <div key={level} className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[11px] text-[#9BA3B0] capitalize">
                {level} ({counts[level as keyof typeof counts]})
              </span>
            </div>
          ))}
        </div>
      </div>
      <SegmentMap className="flex-1 min-h-[500px]" />
    </PageContainer>
  );
}
