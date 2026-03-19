import api from './client';

export interface SegmentFeatureProps {
  id: string;
  name: string;
  pilot: string;
  score: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  speed_limit_kmh: number | null;
  lanes: number | null;
  length_m: number | null;
}

export interface SegmentFeature {
  type: 'Feature';
  geometry: { type: 'LineString'; coordinates: [number, number][] } | null;
  properties: SegmentFeatureProps;
}

export interface SegmentFeatureCollection {
  type: 'FeatureCollection';
  features: SegmentFeature[];
}

export async function fetchSegmentsGeoJSON(pilot?: string): Promise<SegmentFeatureCollection> {
  const { data } = await api.get<SegmentFeatureCollection>('/segments.geojson', {
    params: pilot ? { pilot } : undefined,
  });
  return data;
}
