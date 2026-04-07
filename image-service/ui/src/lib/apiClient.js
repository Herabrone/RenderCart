import axios from 'axios';

const STORAGE_KEY = 'rendercart.apiKey';
const LEGACY_STORAGE_KEY = 'apiKey';
const TOKEN_KEY = 'rendercart.token';
const USER_KEY = 'rendercart.user';
const API_BASE_URL = '/api';

// --- API key helpers (kept for backward compat) ---
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

// --- JWT token helpers ---
export const getStoredToken = () => window.localStorage.getItem(TOKEN_KEY) || '';

export const setStoredToken = (token) => {
  if (!token) {
    clearStoredToken();
    return;
  }
  window.localStorage.setItem(TOKEN_KEY, token);
};

export const clearStoredToken = () => {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
};

export const getStoredUser = () => {
  try {
    return JSON.parse(window.localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
};

export const setStoredUser = (user) => {
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
};

// --- Axios client ---
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const nextConfig = { ...config, headers: { ...(config.headers || {}) } };

  // Prefer JWT token, fall back to API key
  const token = getStoredToken();
  if (token) {
    nextConfig.headers['Authorization'] = `Bearer ${token}`;
  } else {
    const apiKey = getStoredApiKey();
    if (apiKey) {
      nextConfig.headers['X-API-Key'] = apiKey;
    }
  }
  return nextConfig;
});

export const downloadWithAuth = (path, init = {}) => {
  const headers = new Headers(init.headers || {});
  const token = getStoredToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else {
    const apiKey = getStoredApiKey();
    if (apiKey) {
      headers.set('X-API-Key', apiKey);
    }
  }
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
};

// --- Auth API ---
export const registerUser = (email, password, displayName) =>
  apiClient.post('/auth/register', { email, password, display_name: displayName });

export const loginUser = (email, password) =>
  apiClient.post('/auth/login', { email, password });

export const fetchCurrentUser = () => apiClient.get('/auth/me');

// Shopify Store Management API
export const listShopifyStores = () => apiClient.get('/shopify/stores');

export const connectShopifyStore = (authCode, shop) =>
  apiClient.post('/shopify/connect', { authorization_code: authCode, shop });

export const disconnectStore = (storeId) =>
  apiClient.delete(`/shopify/stores/${storeId}`);

// Shopify Product & Inventory API
export const fetchProducts = (storeId, search = '', limit = 20) =>
  apiClient.get(`/shopify/stores/${storeId}/products`, {
    params: { search, limit },
  });

// Shopify Publish API
export const publishAssetToShopify = (assetId, publishRequest) =>
  apiClient.post(`/assets/${assetId}/publish/shopify`, publishRequest);

export const bulkPublishToShopify = (bulkRequest) =>
  apiClient.post('/assets/bulk-publish/shopify', bulkRequest);

export const getPublishStatus = (assetId) =>
  apiClient.get(`/assets/${assetId}/publish-status`);
