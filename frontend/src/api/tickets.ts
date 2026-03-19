import api from './client';

export interface Ticket {
  id: number;
  asset_id: string;
  detection_id: number | null;
  pilot: string;
  status: string;
  priority: number;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export async function fetchTickets(status?: string, limit = 50): Promise<Ticket[]> {
  const { data } = await api.get<Ticket[]>('/tickets', { params: { status, limit } });
  return data;
}

export async function updateTicket(id: number, status: string): Promise<Ticket> {
  const { data } = await api.patch<Ticket>(`/tickets/${id}`, { status });
  return data;
}
