import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach auth token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 by trying refresh, then redirecting to login
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

client.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config;
    if (err.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        originalRequest._retry = true;
        if (!isRefreshing) {
          isRefreshing = true;
          try {
            const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            onRefreshed(data.access_token);
            isRefreshing = false;
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            return client(originalRequest);
          } catch {
            isRefreshing = false;
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.dispatchEvent(new CustomEvent('auth:logout'));
          }
        } else {
          return new Promise((resolve) => {
            refreshSubscribers.push((token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(client(originalRequest));
            });
          });
        }
      }
    }
    const msg = err.response?.data?.detail || err.message || '请求失败';
    return Promise.reject(new Error(msg));
  },
);

export default client;

// Token helpers
export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function getAccessToken() {
  return localStorage.getItem('access_token');
}
