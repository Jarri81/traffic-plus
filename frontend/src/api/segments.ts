import api from './client';

export interface Segment {
  id: string;
  pilot: string;
  name: string | null;
  length_m: number | null;
  speed_limit_kmh: number | null;
  road_class: string | null;
  lanes: number | null;
  created_at: string;
  updated_at: string;
}

export async function fetchSegments(skip = 0, limit = 100): Promise<Segment[]> {
  const { data } = await api.get<Segment[]>('/segments', { params: { skip, limit } });
  return data;
}

export async function fetchSegment(id: string): Promise<Segment> {
  const { data } = await api.get<Segment>(`/segments/${id}`);
  return data;
}
