import { useQuery } from '@tanstack/react-query';
import { fetchWeather } from '../api/weather';

export function useWeather() {
  return useQuery({
    queryKey: ['weather'],
    queryFn: fetchWeather,
    staleTime: 5 * 60_000,      // weather stays fresh 5 min
    refetchInterval: 10 * 60_000, // re-fetch every 10 min
  });
}
