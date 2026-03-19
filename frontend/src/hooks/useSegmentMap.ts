import { useQuery } from '@tanstack/react-query';
import { fetchSegmentsGeoJSON } from '../api/geojson';

export function useSegmentsGeoJSON(pilot?: string) {
  return useQuery({
    queryKey: ['segments-geojson', pilot],
    queryFn: () => fetchSegmentsGeoJSON(pilot),
    staleTime: 60_000,
  });
}
