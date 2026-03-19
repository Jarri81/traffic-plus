import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchIncidents } from '../api/alerts';
import api from '../api/client';

export function useIncidents(status?: string) {
  return useQuery({
    queryKey: ['incidents', status],
    queryFn: () => fetchIncidents(status),
  });
}

export function useResolveIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.patch(`/incidents/${id}/resolve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
    },
  });
}
