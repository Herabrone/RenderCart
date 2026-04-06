import axios from 'axios';

const STORAGE_KEY = 'rendercart.apiKey';
const LEGACY_STORAGE_KEY = 'apiKey';
const API_BASE_URL = '/api';

export const getStoredApiKey = () =>
  window.localStorage.getItem(STORAGE_KEY) || window.localStorage.getItem(LEGACY_STORAGE_KEY) || '';

export const setStoredApiKey = (apiKey) => {
  const trimmed = apiKey.trim();
  if (!trimmed) {
    clearStoredApiKey();
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, trimmed);
  window.localStorage.setItem(LEGACY_STORAGE_KEY, trimmed);
};

export const clearStoredApiKey = () => {
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const apiKey = getStoredApiKey();
  const nextConfig = { ...config, headers: { ...(config.headers || {}) } };
  if (apiKey) {
    nextConfig.headers['X-API-Key'] = apiKey;
  }
  return nextConfig;
});

export const downloadWithAuth = (path, init = {}) => {
  const headers = new Headers(init.headers || {});
  const apiKey = getStoredApiKey();
  if (apiKey) {
    headers.set('X-API-Key', apiKey);
  }
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
};
