/**
 * Silent token refresh.
 *
 * The access token expires in 30 minutes. This module schedules a refresh
 * at 25 minutes so the user is never logged out mid-session.
 *
 * Call startTokenRefresh() once after login.
 * Call stopTokenRefresh() on logout.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000; // refresh 5 min before expiry

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

function parseExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

async function doRefresh(): Promise<void> {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/refresh?token=${encodeURIComponent(token)}`, {
      method: 'POST',
    });
    if (!res.ok) {
      // Token invalid — clear and let the 401 interceptor handle redirect
      localStorage.removeItem('access_token');
      return;
    }
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    scheduleRefresh(data.access_token);
  } catch {
    // Network error — don't clear token, retry will happen on next API call
  }
}

function scheduleRefresh(token: string): void {
  if (refreshTimer) clearTimeout(refreshTimer);

  const expiry = parseExpiry(token);
  if (!expiry) return;

  const msUntilRefresh = expiry - Date.now() - REFRESH_BEFORE_EXPIRY_MS;
  if (msUntilRefresh <= 0) {
    // Already close to expiry — refresh immediately
    doRefresh();
    return;
  }

  refreshTimer = setTimeout(doRefresh, msUntilRefresh);
}

export function startTokenRefresh(): void {
  const token = localStorage.getItem('access_token');
  if (token) scheduleRefresh(token);
}

export function stopTokenRefresh(): void {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}
