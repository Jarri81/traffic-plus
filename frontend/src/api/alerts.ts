import api from './client';

export interface Incident {
  id: number;
  pilot: string;
  incident_type: string;
  severity: number | null;
  status: string;
  segment_id: string | null;
  description: string | null;
  source: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
}

export async function fetchIncidents(status?: string, limit = 50): Promise<Incident[]> {
  const { data } = await api.get<Incident[]>('/incidents', {
    params: { status, limit },
  });
  return data;
}
