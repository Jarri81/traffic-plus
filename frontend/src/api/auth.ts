import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserOut {
  id: string;
  email: string;
  name: string | null;
  role: string;
  pilot_scope: string | null;
  is_active: boolean;
  created_at: string;
}

/** Login using OAuth2 password flow. Returns token and stores it. */
export async function login(email: string, password: string): Promise<TokenResponse> {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  const { data } = await axios.post<TokenResponse>(
    `${BASE_URL}/api/v1/auth/token`,
    params,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  localStorage.setItem('access_token', data.access_token);
  return data;
}

export async function register(email: string, password: string, name?: string): Promise<UserOut> {
  const { data } = await axios.post<UserOut>(`${BASE_URL}/api/v1/auth/register`, {
    email, password, name,
  });
  return data;
}

export function logout(): void {
  localStorage.removeItem('access_token');
}

export function getToken(): string | null {
  return localStorage.getItem('access_token');
}
