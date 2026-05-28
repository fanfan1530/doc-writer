import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach auth token
client.interceptors.request.use((config) => {
  const token = getAccessToken();
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
      const persistentFlag = localStorage.getItem('token_persistent') === '1';
      const storage = persistentFlag ? localStorage : sessionStorage;
      const refreshToken = storage.getItem('refresh_token');
      if (refreshToken) {
        originalRequest._retry = true;
        if (!isRefreshing) {
          isRefreshing = true;
          try {
            const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
            storage.setItem('access_token', data.access_token);
            storage.setItem('refresh_token', data.refresh_token);
            onRefreshed(data.access_token);
            isRefreshing = false;
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            return client(originalRequest);
          } catch {
            isRefreshing = false;
            clearTokens();
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
    // 增强错误对象：保留 HTTP 状态码和类型，兼容已有 Error.message 模式
    const msg = err.response?.data?.detail || err.message || '请求失败';
    const appErr = new Error(msg) as Error & { code: number; type: string };
    appErr.code = err.response?.status || 0;
    if (appErr.code >= 400 && appErr.code < 500) {
      appErr.type = appErr.code === 422 ? 'validation' : 'business';
    } else if (appErr.code >= 500) {
      appErr.type = 'server';
    } else if (err.code === 'ECONNABORTED' || err.code === 'ERR_NETWORK') {
      appErr.type = 'network';
    } else {
      appErr.type = 'unknown';
    }
    return Promise.reject(appErr);
  },
);

export default client;

// Token helpers
function getStorage(persistent: boolean): Storage {
  return persistent ? localStorage : sessionStorage;
}

export function setTokens(access: string, refresh: string, persistent = false) {
  const storage = getStorage(persistent);
  storage.setItem('access_token', access);
  storage.setItem('refresh_token', refresh);
  // Also keep a flag so the rest of the code knows where to read
  localStorage.setItem('token_persistent', persistent ? '1' : '0');
}

export function clearTokens() {
  [localStorage, sessionStorage].forEach((s) => {
    s.removeItem('access_token');
    s.removeItem('refresh_token');
  });
  localStorage.removeItem('token_persistent');
}

export function getAccessToken() {
  const persistent = localStorage.getItem('token_persistent') === '1';
  const storage = persistent ? localStorage : sessionStorage;
  return storage.getItem('access_token');
}
