import api from './client';

export interface RiskScore {
  segment_id: string;
  score: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  factors: Record<string, number>;
  computed_at: string;
}

export interface RiskSummaryItem {
  segment_id: string;
  score: number;
  level: string;
}

export async function fetchRisk(segmentId: string): Promise<RiskScore> {
  const { data } = await api.get<RiskScore>(`/risk/${segmentId}`);
  return data;
}

export async function fetchRiskSummary(): Promise<RiskSummaryItem[]> {
  const { data } = await api.get<RiskSummaryItem[]>('/risk/summary');
  return data;
}
