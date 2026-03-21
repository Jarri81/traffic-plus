import api from './client';

export interface AppUser {
  id: string;
  email: string;
  name: string | null;
  role: 'viewer' | 'operator' | 'admin';
  pilot_scope: string | null;
  is_active: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  name?: string;
  role?: 'viewer' | 'operator' | 'admin';
}

export async function fetchUsers(): Promise<AppUser[]> {
  const { data } = await api.get<AppUser[]>('/users');
  return data;
}

export async function createUser(body: UserCreate): Promise<AppUser> {
  const { data } = await api.post<AppUser>('/users', body);
  return data;
}

export async function updateUserRole(id: string, role: string): Promise<AppUser> {
  const { data } = await api.patch<AppUser>(`/users/${id}/role`, { role });
  return data;
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/users/${id}`);
}
