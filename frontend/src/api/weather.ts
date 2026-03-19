/**
 * Open-Meteo API — free, no token required.
 * Docs: https://open-meteo.com/en/docs
 *
 * Coordinates default to Madrid. Override via VITE_WEATHER_LAT / VITE_WEATHER_LON.
 */

const LAT = import.meta.env.VITE_WEATHER_LAT ?? '40.4168';
const LON = import.meta.env.VITE_WEATHER_LON ?? '-3.7038';

export interface CurrentWeather {
  temperature: number;
  humidity: number;
  windSpeed: number;
  visibility: number;   // km
  precipitation: number; // mm
  condition: string;
}

export interface ForecastPoint {
  time: string;
  temp: number;
  precipitation: number;
  windSpeed: number;
  riskImpact: number;
}

function deriveCondition(temp: number, precip: number, wind: number): string {
  if (precip > 2) return 'Heavy Rain';
  if (precip > 0.5) return 'Light Rain';
  if (wind > 50) return 'Strong Winds';
  if (temp > 30) return 'Hot & Sunny';
  if (temp < 5) return 'Cold';
  return 'Partly Cloudy';
}

function calcRiskImpact(precip: number, wind: number, vis: number): number {
  // mirrors backend weather risk factor formula
  const precipScore = Math.min(precip / 10, 1) * 40;
  const windScore = Math.min(wind / 60, 1) * 30;
  const visKm = vis / 1000;
  const visScore = visKm < 10 ? (1 - Math.min(visKm / 10, 1)) * 30 : 0;
  return Math.round(Math.min(precipScore + windScore + visScore, 100));
}

export async function fetchWeather(): Promise<{ current: CurrentWeather; forecast: ForecastPoint[] }> {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${LAT}&longitude=${LON}` +
    `&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,visibility` +
    `&hourly=temperature_2m,precipitation,wind_speed_10m,visibility` +
    `&forecast_days=2&timezone=auto`;

  const res = await fetch(url);
  if (!res.ok) throw new Error('Weather API error');
  const data = await res.json();

  const c = data.current;
  const visKm = (c.visibility ?? 10000) / 1000;

  const current: CurrentWeather = {
    temperature: Math.round(c.temperature_2m ?? 0),
    humidity: Math.round(c.relative_humidity_2m ?? 0),
    windSpeed: Math.round(c.wind_speed_10m ?? 0),
    visibility: Math.round(visKm * 10) / 10,
    precipitation: Math.round((c.precipitation ?? 0) * 10) / 10,
    condition: deriveCondition(c.temperature_2m, c.precipitation, c.wind_speed_10m),
  };

  const hourly = data.hourly;
  const forecast: ForecastPoint[] = (hourly.time as string[])
    .slice(0, 25)
    .map((_t: string, i: number) => {
      const vis = (hourly.visibility?.[i] ?? 10000);
      const precip = hourly.precipitation?.[i] ?? 0;
      const wind = hourly.wind_speed_10m?.[i] ?? 0;
      const label = `+${i}h`;
      return {
        time: label,
        temp: Math.round(hourly.temperature_2m?.[i] ?? 0),
        precipitation: Math.round(precip * 10) / 10,
        windSpeed: Math.round(wind),
        riskImpact: calcRiskImpact(precip, wind, vis),
      };
    });

  return { current, forecast };
}
