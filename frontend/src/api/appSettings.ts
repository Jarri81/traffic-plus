import api from './client';

export interface AppSettings {
  webhook_url: string;
}

export async function fetchAppSettings(): Promise<AppSettings> {
  const { data } = await api.get<AppSettings>('/settings');
  return data;
}

export async function updateAppSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  const { data } = await api.patch<AppSettings>('/settings', settings);
  return data;
}
