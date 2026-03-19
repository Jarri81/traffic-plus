import { useQuery } from '@tanstack/react-query';
import { fetchSegments } from '../api/segments';
import { fetchRiskSummary } from '../api/risk';

export function useSegments() {
  return useQuery({ queryKey: ['segments'], queryFn: () => fetchSegments() });
}

export function useRiskSummary() {
  return useQuery({ queryKey: ['risk-summary'], queryFn: fetchRiskSummary });
}

/** Returns a map of segment_id → { score, level } for fast lookups. */
export function useRiskMap() {
  const { data } = useRiskSummary();
  if (!data) return {};
  return Object.fromEntries(data.map((r) => [r.segment_id, r]));
}
